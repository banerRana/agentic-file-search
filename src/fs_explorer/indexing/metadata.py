"""
Metadata extraction helpers for indexed documents.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


_CURRENCY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4})\b",
    flags=re.IGNORECASE,
)

_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agreement": ("agreement", "purchase"),
    "schedule": ("schedule", "exhibit"),
    "report": ("report", "assessment", "audit"),
    "legal": ("legal", "opinion", "nda"),
    "financial": ("financial", "escrow", "pricing", "adjustment"),
    "checklist": ("checklist", "closing"),
}


def infer_document_type(file_path: str) -> str:
    """Infer a coarse document type from filename keywords."""
    stem = Path(file_path).stem.lower()
    for doc_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in stem for keyword in keywords):
            return doc_type
    return "other"


def extract_metadata(
    *,
    file_path: str,
    root_path: str,
    content: str,
    schema_def: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build metadata used for filtering and schema-aware indexing.

    If a schema is provided with a `fields` list, only those keys are emitted.
    """
    absolute_path = str(Path(file_path).resolve())
    relative_path = os.path.relpath(absolute_path, str(Path(root_path).resolve()))
    extension = Path(file_path).suffix.lower()

    stat = os.stat(file_path)
    metadata: dict[str, Any] = {
        "filename": Path(file_path).name,
        "relative_path": relative_path,
        "extension": extension,
        "document_type": infer_document_type(file_path),
        "file_size_bytes": int(stat.st_size),
        "file_mtime": float(stat.st_mtime),
        "mentions_currency": bool(_CURRENCY_RE.search(content)),
        "mentions_dates": bool(_DATE_RE.search(content)),
    }

    if not schema_def:
        return metadata

    fields = schema_def.get("fields")
    if not isinstance(fields, list):
        return metadata

    allowed: set[str] = set()
    for field in fields:
        if isinstance(field, dict):
            name = field.get("name")
            if isinstance(name, str):
                allowed.add(name)

    if not allowed:
        return metadata

    return {k: v for k, v in metadata.items() if k in allowed}
