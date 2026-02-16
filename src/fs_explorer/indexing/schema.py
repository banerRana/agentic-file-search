"""
Schema discovery utilities.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .metadata import infer_document_type
from ..fs import SUPPORTED_EXTENSIONS


def _iter_supported_files(folder: str) -> list[str]:
    root = Path(folder).resolve()
    files: list[str] = []
    for current_root, _, filenames in os.walk(root):
        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(str(Path(current_root) / filename))
    files.sort()
    return files


class SchemaDiscovery:
    """Auto-discover a lightweight metadata schema from a corpus."""

    def discover_from_folder(self, folder: str) -> dict[str, Any]:
        files = _iter_supported_files(folder)
        document_types = sorted({infer_document_type(path) for path in files})
        corpus_name = Path(folder).resolve().name or "corpus"

        fields: list[dict[str, Any]] = [
            {
                "name": "filename",
                "type": "string",
                "required": True,
                "description": "Document filename.",
            },
            {
                "name": "relative_path",
                "type": "string",
                "required": True,
                "description": "Path relative to corpus root.",
            },
            {
                "name": "extension",
                "type": "string",
                "required": True,
                "description": "File extension.",
            },
            {
                "name": "document_type",
                "type": "string",
                "required": True,
                "description": "Inferred document category.",
                "enum": document_types or ["other"],
            },
            {
                "name": "file_size_bytes",
                "type": "integer",
                "required": True,
                "description": "File size in bytes.",
            },
            {
                "name": "file_mtime",
                "type": "number",
                "required": True,
                "description": "File modification timestamp (epoch seconds).",
            },
            {
                "name": "mentions_currency",
                "type": "boolean",
                "required": True,
                "description": "Whether text appears to contain currency amounts.",
            },
            {
                "name": "mentions_dates",
                "type": "boolean",
                "required": True,
                "description": "Whether text appears to contain date patterns.",
            },
        ]

        return {
            "name": f"auto_{corpus_name}",
            "description": "Auto-discovered schema for document-level metadata filtering.",
            "fields": fields,
        }
