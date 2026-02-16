"""
DuckDB storage backend for index persistence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from .base import ChunkRecord, DocumentRecord, SchemaRecord


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


class DuckDBStorage:
    """DuckDB-backed persistence for corpora, documents, chunks, and schemas."""

    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).expanduser().resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self.db_path)
        self.initialize()

    def initialize(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS corpora (
                id VARCHAR PRIMARY KEY,
                root_path VARCHAR NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id VARCHAR PRIMARY KEY,
                corpus_id VARCHAR NOT NULL REFERENCES corpora(id),
                relative_path VARCHAR NOT NULL,
                absolute_path VARCHAR NOT NULL,
                content VARCHAR NOT NULL,
                metadata_json VARCHAR NOT NULL DEFAULT '{}',
                file_mtime DOUBLE NOT NULL,
                file_size BIGINT NOT NULL,
                content_sha256 VARCHAR NOT NULL,
                last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,
                UNIQUE(corpus_id, relative_path)
            );
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id VARCHAR PRIMARY KEY,
                doc_id VARCHAR NOT NULL REFERENCES documents(id),
                text VARCHAR NOT NULL,
                position INTEGER NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL
            );
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schemas (
                id VARCHAR PRIMARY KEY,
                corpus_id VARCHAR NOT NULL REFERENCES corpora(id),
                name VARCHAR NOT NULL,
                schema_def VARCHAR NOT NULL,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(corpus_id, name)
            );
            """
        )

    def get_or_create_corpus(self, root_path: str) -> str:
        normalized = str(Path(root_path).resolve())
        corpus_id = _stable_id("corpus", normalized)
        self._conn.execute(
            """
            INSERT INTO corpora (id, root_path)
            VALUES (?, ?)
            ON CONFLICT(root_path) DO NOTHING
            """,
            [corpus_id, normalized],
        )
        row = self._conn.execute(
            "SELECT id FROM corpora WHERE root_path = ?",
            [normalized],
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to create corpus for path: {normalized}")
        return str(row[0])

    def get_corpus_id(self, root_path: str) -> str | None:
        normalized = str(Path(root_path).resolve())
        row = self._conn.execute(
            "SELECT id FROM corpora WHERE root_path = ?",
            [normalized],
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def upsert_document(self, document: DocumentRecord, chunks: list[ChunkRecord]) -> None:
        # Remove old chunks first to avoid FK limitations on upsert updates in DuckDB.
        self._conn.execute("DELETE FROM chunks WHERE doc_id = ?", [document.id])

        self._conn.execute(
            """
            INSERT INTO documents (
                id, corpus_id, relative_path, absolute_path, content, metadata_json,
                file_mtime, file_size, content_sha256, is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT(id) DO UPDATE SET
                corpus_id = excluded.corpus_id,
                relative_path = excluded.relative_path,
                absolute_path = excluded.absolute_path,
                content = excluded.content,
                metadata_json = excluded.metadata_json,
                file_mtime = excluded.file_mtime,
                file_size = excluded.file_size,
                content_sha256 = excluded.content_sha256,
                last_indexed_at = now(),
                is_deleted = FALSE
            """,
            [
                document.id,
                document.corpus_id,
                document.relative_path,
                document.absolute_path,
                document.content,
                document.metadata_json,
                document.file_mtime,
                document.file_size,
                document.content_sha256,
            ],
        )

        if chunks:
            self._conn.executemany(
                """
                INSERT INTO chunks (id, doc_id, text, position, start_char, end_char)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.doc_id,
                        chunk.text,
                        chunk.position,
                        chunk.start_char,
                        chunk.end_char,
                    )
                    for chunk in chunks
                ],
            )

    def mark_deleted_missing_documents(
        self,
        *,
        corpus_id: str,
        active_relative_paths: set[str],
    ) -> int:
        if not active_relative_paths:
            self._conn.execute(
                """
                UPDATE documents
                SET is_deleted = TRUE
                WHERE corpus_id = ? AND is_deleted = FALSE
                """,
                [corpus_id],
            )
        else:
            placeholders = ", ".join(["?"] * len(active_relative_paths))
            params: list[Any] = [corpus_id]
            params.extend(sorted(active_relative_paths))
            self._conn.execute(
                f"""
                UPDATE documents
                SET is_deleted = TRUE
                WHERE corpus_id = ?
                  AND is_deleted = FALSE
                  AND relative_path NOT IN ({placeholders})
                """,
                params,
            )

        row = self._conn.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE corpus_id = ? AND is_deleted = TRUE
            """,
            [corpus_id],
        ).fetchone()
        return int(row[0]) if row else 0

    def list_documents(
        self,
        *,
        corpus_id: str,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, relative_path, absolute_path, file_size, file_mtime, is_deleted
            FROM documents
            WHERE corpus_id = ?
        """
        params: list[Any] = [corpus_id]
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        sql += " ORDER BY relative_path"

        rows = self._conn.execute(sql, params).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": str(row[0]),
                    "relative_path": str(row[1]),
                    "absolute_path": str(row[2]),
                    "file_size": int(row[3]),
                    "file_mtime": float(row[4]),
                    "is_deleted": bool(row[5]),
                }
            )
        return results

    def count_chunks(self, *, corpus_id: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*)
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE d.corpus_id = ? AND d.is_deleted = FALSE
            """,
            [corpus_id],
        ).fetchone()
        return int(row[0]) if row else 0

    def save_schema(
        self,
        *,
        corpus_id: str,
        name: str,
        schema_def: dict[str, Any],
        is_active: bool = True,
    ) -> str:
        schema_id = _stable_id("schema", f"{corpus_id}:{name}")
        if is_active:
            self._conn.execute(
                "UPDATE schemas SET is_active = FALSE WHERE corpus_id = ?",
                [corpus_id],
            )

        self._conn.execute(
            """
            INSERT INTO schemas (id, corpus_id, name, schema_def, is_active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(corpus_id, name) DO UPDATE SET
                schema_def = excluded.schema_def,
                is_active = excluded.is_active
            """,
            [
                schema_id,
                corpus_id,
                name,
                json.dumps(schema_def, sort_keys=True),
                is_active,
            ],
        )
        return schema_id

    def list_schemas(self, *, corpus_id: str) -> list[SchemaRecord]:
        rows = self._conn.execute(
            """
            SELECT id, corpus_id, name, schema_def, is_active, created_at
            FROM schemas
            WHERE corpus_id = ?
            ORDER BY created_at DESC, name ASC
            """,
            [corpus_id],
        ).fetchall()
        return [self._row_to_schema_record(row) for row in rows]

    def get_schema_by_name(self, *, corpus_id: str, name: str) -> SchemaRecord | None:
        row = self._conn.execute(
            """
            SELECT id, corpus_id, name, schema_def, is_active, created_at
            FROM schemas
            WHERE corpus_id = ? AND name = ?
            LIMIT 1
            """,
            [corpus_id, name],
        ).fetchone()
        if row is None:
            return None
        return self._row_to_schema_record(row)

    def get_active_schema(self, *, corpus_id: str) -> SchemaRecord | None:
        row = self._conn.execute(
            """
            SELECT id, corpus_id, name, schema_def, is_active, created_at
            FROM schemas
            WHERE corpus_id = ? AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [corpus_id],
        ).fetchone()
        if row is None:
            return None
        return self._row_to_schema_record(row)

    @staticmethod
    def make_document_id(corpus_id: str, relative_path: str) -> str:
        return _stable_id("doc", f"{corpus_id}:{relative_path}")

    @staticmethod
    def make_chunk_id(doc_id: str, position: int, start_char: int, end_char: int) -> str:
        return _stable_id("chunk", f"{doc_id}:{position}:{start_char}:{end_char}")

    @staticmethod
    def _row_to_schema_record(row: tuple[Any, ...]) -> SchemaRecord:
        return SchemaRecord(
            id=str(row[0]),
            corpus_id=str(row[1]),
            name=str(row[2]),
            schema_def=json.loads(str(row[3])),
            is_active=bool(row[4]),
            created_at=str(row[5]),
        )
