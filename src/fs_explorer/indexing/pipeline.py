"""
Indexing pipeline orchestration.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chunker import SmartChunker
from .metadata import (
    ensure_langextract_schema_fields,
    extract_metadata,
    langextract_field_names,
)
from .schema import SchemaDiscovery
from ..fs import SUPPORTED_EXTENSIONS, parse_file
from ..storage import ChunkRecord, DocumentRecord, DuckDBStorage, StorageBackend

_PARSE_ERROR_PREFIXES: tuple[str, ...] = (
    "Error parsing ",
    "Unsupported file extension",
    "No such file:",
)


@dataclass(frozen=True)
class IndexingResult:
    """Summary output for an indexing run."""

    corpus_id: str
    indexed_files: int
    skipped_files: int
    deleted_files: int
    chunks_written: int
    active_documents: int
    schema_used: str | None


class IndexingPipeline:
    """Build and update corpus indexes from filesystem documents."""

    def __init__(
        self,
        storage: StorageBackend,
        chunker: SmartChunker | None = None,
    ) -> None:
        self.storage = storage
        self.chunker = chunker or SmartChunker()

    def index_folder(
        self,
        folder: str,
        *,
        discover_schema: bool = False,
        schema_name: str | None = None,
        with_metadata: bool = False,
    ) -> IndexingResult:
        root = str(Path(folder).resolve())
        if not os.path.exists(root) or not os.path.isdir(root):
            raise ValueError(f"No such directory: {root}")

        corpus_id = self.storage.get_or_create_corpus(root)
        schema_def, selected_schema_name = self._resolve_schema(
            corpus_id=corpus_id,
            root=root,
            discover_schema=discover_schema,
            schema_name=schema_name,
            with_metadata=with_metadata,
        )

        indexed_files = 0
        skipped_files = 0
        chunks_written = 0
        active_paths: set[str] = set()

        for file_path in self._iter_supported_files(root):
            relative_path = os.path.relpath(file_path, root)
            active_paths.add(relative_path)

            content = parse_file(file_path)
            if self._is_parse_error(content):
                skipped_files += 1
                continue

            chunks = self.chunker.chunk_text(content)
            metadata = extract_metadata(
                file_path=file_path,
                root_path=root,
                content=content,
                schema_def=schema_def,
                with_langextract=with_metadata,
            )
            metadata_json = json.dumps(metadata, sort_keys=True)

            stat = os.stat(file_path)
            doc_id = DuckDBStorage.make_document_id(corpus_id, relative_path)
            doc_record = DocumentRecord(
                id=doc_id,
                corpus_id=corpus_id,
                relative_path=relative_path,
                absolute_path=str(Path(file_path).resolve()),
                content=content,
                metadata_json=metadata_json,
                file_mtime=float(stat.st_mtime),
                file_size=int(stat.st_size),
                content_sha256=self._sha256(content),
            )

            chunk_records: list[ChunkRecord] = []
            for chunk in chunks:
                chunk_records.append(
                    ChunkRecord(
                        id=DuckDBStorage.make_chunk_id(
                            doc_id,
                            chunk.position,
                            chunk.start_char,
                            chunk.end_char,
                        ),
                        doc_id=doc_id,
                        text=chunk.text,
                        position=chunk.position,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                    )
                )

            self.storage.upsert_document(doc_record, chunk_records)
            indexed_files += 1
            chunks_written += len(chunk_records)

        deleted_files = self.storage.mark_deleted_missing_documents(
            corpus_id=corpus_id,
            active_relative_paths=active_paths,
        )
        active_documents = len(
            self.storage.list_documents(corpus_id=corpus_id, include_deleted=False)
        )

        return IndexingResult(
            corpus_id=corpus_id,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            deleted_files=deleted_files,
            chunks_written=chunks_written,
            active_documents=active_documents,
            schema_used=selected_schema_name,
        )

    def _resolve_schema(
        self,
        *,
        corpus_id: str,
        root: str,
        discover_schema: bool,
        schema_name: str | None,
        with_metadata: bool,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if discover_schema:
            schema_def = SchemaDiscovery().discover_from_folder(
                root,
                with_langextract=with_metadata,
            )
            discovered_name = str(schema_def.get("name", f"auto_{Path(root).name}"))
            self.storage.save_schema(
                corpus_id=corpus_id,
                name=discovered_name,
                schema_def=schema_def,
                is_active=True,
            )
            return schema_def, discovered_name

        if schema_name:
            schema = self.storage.get_schema_by_name(corpus_id=corpus_id, name=schema_name)
            if schema is None:
                raise ValueError(f"Schema '{schema_name}' not found for corpus {root}")
            if with_metadata:
                return self._augment_schema_for_langextract(
                    corpus_id=corpus_id,
                    schema_name=schema.name,
                    schema_def=schema.schema_def,
                )
            return schema.schema_def, schema.name

        active = self.storage.get_active_schema(corpus_id=corpus_id)
        if active is None:
            if with_metadata:
                schema_def = SchemaDiscovery().discover_from_folder(
                    root,
                    with_langextract=True,
                )
                discovered_name = str(schema_def.get("name", f"auto_{Path(root).name}"))
                self.storage.save_schema(
                    corpus_id=corpus_id,
                    name=discovered_name,
                    schema_def=schema_def,
                    is_active=True,
                )
                return schema_def, discovered_name
            return None, None
        if with_metadata:
            return self._augment_schema_for_langextract(
                corpus_id=corpus_id,
                schema_name=active.name,
                schema_def=active.schema_def,
            )
        return active.schema_def, active.name

    def _augment_schema_for_langextract(
        self,
        *,
        corpus_id: str,
        schema_name: str,
        schema_def: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        existing_field_names = self._schema_field_names(schema_def)
        required = langextract_field_names()
        if required.issubset(existing_field_names):
            return schema_def, schema_name

        augmented_schema, _ = ensure_langextract_schema_fields(schema_def)
        self.storage.save_schema(
            corpus_id=corpus_id,
            name=schema_name,
            schema_def=augmented_schema,
            is_active=True,
        )
        return augmented_schema, schema_name

    @staticmethod
    def _schema_field_names(schema_def: dict[str, Any]) -> set[str]:
        fields = schema_def.get("fields")
        if not isinstance(fields, list):
            return set()
        names: set[str] = set()
        for field in fields:
            if isinstance(field, dict):
                name = field.get("name")
                if isinstance(name, str):
                    names.add(name)
        return names

    @staticmethod
    def _iter_supported_files(root: str) -> list[str]:
        files: list[str] = []
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(str(Path(current_root) / filename))
        files.sort()
        return files

    @staticmethod
    def _sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_parse_error(content: str) -> bool:
        return content.startswith(_PARSE_ERROR_PREFIXES)
