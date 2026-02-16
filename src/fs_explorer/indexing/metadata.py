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

_LANGEXTRACT_PROMPT_DESCRIPTION = (
    "Extract key transaction metadata from legal and deal documents. "
    "Use extraction classes: organization, person, money, date, deal_term. "
    "Use exact spans from the source text and avoid paraphrasing."
)

LANGEXTRACT_FIELD_DEFS: tuple[dict[str, Any], ...] = (
    {
        "name": "lx_enabled",
        "type": "boolean",
        "required": False,
        "description": "Whether langextract metadata extraction succeeded.",
    },
    {
        "name": "lx_extraction_count",
        "type": "integer",
        "required": False,
        "description": "Number of langextract entities extracted from the document.",
    },
    {
        "name": "lx_entity_classes",
        "type": "string",
        "required": False,
        "description": "Comma-separated extraction classes returned by langextract.",
    },
    {
        "name": "lx_organizations",
        "type": "string",
        "required": False,
        "description": "Comma-separated organization names extracted by langextract.",
    },
    {
        "name": "lx_people",
        "type": "string",
        "required": False,
        "description": "Comma-separated person names extracted by langextract.",
    },
    {
        "name": "lx_deal_terms",
        "type": "string",
        "required": False,
        "description": "Comma-separated deal terms extracted by langextract.",
    },
    {
        "name": "lx_money_mentions",
        "type": "integer",
        "required": False,
        "description": "Count of monetary amount entities from langextract.",
    },
    {
        "name": "lx_date_mentions",
        "type": "integer",
        "required": False,
        "description": "Count of date entities from langextract.",
    },
    {
        "name": "lx_has_earnout",
        "type": "boolean",
        "required": False,
        "description": "Whether extracted deal terms indicate an earnout.",
    },
    {
        "name": "lx_has_escrow",
        "type": "boolean",
        "required": False,
        "description": "Whether extracted deal terms indicate escrow.",
    },
)


def infer_document_type(file_path: str) -> str:
    """Infer a coarse document type from filename keywords."""
    stem = Path(file_path).stem.lower()
    for doc_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in stem for keyword in keywords):
            return doc_type
    return "other"


def langextract_schema_fields() -> list[dict[str, Any]]:
    """Return schema field definitions for langextract metadata."""
    return [dict(field) for field in LANGEXTRACT_FIELD_DEFS]


def langextract_field_names() -> set[str]:
    """Return field names used by langextract metadata extraction."""
    return {field["name"] for field in LANGEXTRACT_FIELD_DEFS}


def ensure_langextract_schema_fields(schema_def: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Ensure schema contains langextract field definitions."""
    fields_obj = schema_def.get("fields")
    fields: list[dict[str, Any]]
    if isinstance(fields_obj, list):
        fields = [dict(field) for field in fields_obj if isinstance(field, dict)]
    else:
        fields = []

    existing_names = {
        str(field.get("name"))
        for field in fields
        if isinstance(field.get("name"), str)
    }
    updated = list(fields)
    changed = False
    for field in LANGEXTRACT_FIELD_DEFS:
        if field["name"] in existing_names:
            continue
        updated.append(dict(field))
        changed = True

    if not changed:
        return dict(schema_def), False
    merged = dict(schema_def)
    merged["fields"] = updated
    return merged, True


def extract_metadata(
    *,
    file_path: str,
    root_path: str,
    content: str,
    schema_def: dict[str, Any] | None = None,
    with_langextract: bool = False,
    langextract_model_id: str | None = None,
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
    if with_langextract:
        metadata.update(
            _extract_langextract_metadata(
                content=content,
                model_id=langextract_model_id,
            )
        )

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


def _extract_langextract_metadata(
    *,
    content: str,
    model_id: str | None = None,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "lx_enabled": False,
        "lx_extraction_count": 0,
        "lx_entity_classes": "",
        "lx_organizations": "",
        "lx_people": "",
        "lx_deal_terms": "",
        "lx_money_mentions": 0,
        "lx_date_mentions": 0,
        "lx_has_earnout": False,
        "lx_has_escrow": False,
    }
    api_key = (
        os.getenv("LANGEXTRACT_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        return defaults

    try:
        import langextract as lx  # type: ignore[import-not-found]
    except Exception:
        return defaults

    max_chars = _safe_int_env("FS_EXPLORER_LANGEXTRACT_MAX_CHARS", default=6000, minimum=500)
    snippet = content[:max_chars]
    if not snippet.strip():
        return defaults

    effective_model_id = model_id or os.getenv(
        "FS_EXPLORER_LANGEXTRACT_MODEL",
        "gemini-3-flash-preview",
    )
    try:
        result = lx.extract(
            text_or_documents=snippet,
            prompt_description=_LANGEXTRACT_PROMPT_DESCRIPTION,
            examples=_langextract_examples(lx),
            model_id=effective_model_id,
            api_key=api_key,
            max_char_buffer=min(1200, max_chars),
            show_progress=False,
            prompt_validation_level=lx.prompt_validation.PromptValidationLevel.OFF,
        )
    except Exception:
        return defaults

    extractions = list(result.extractions or [])
    if not extractions:
        return {**defaults, "lx_enabled": True}

    classes: set[str] = set()
    organizations: list[str] = []
    people: list[str] = []
    terms: list[str] = []
    money_mentions = 0
    date_mentions = 0

    for extraction in extractions:
        extraction_class = str(extraction.extraction_class).strip().lower()
        extraction_text = str(extraction.extraction_text).strip()
        if not extraction_text:
            continue
        classes.add(extraction_class)
        if extraction_class in {"organization", "company", "party"}:
            organizations.append(extraction_text)
        elif extraction_class in {"person", "individual", "executive"}:
            people.append(extraction_text)
        elif extraction_class in {"deal_term", "term", "provision"}:
            terms.append(extraction_text)
        elif extraction_class in {"money", "amount", "currency"}:
            money_mentions += 1
        elif extraction_class == "date":
            date_mentions += 1

    normalized_terms = [term.lower() for term in terms]
    return {
        "lx_enabled": True,
        "lx_extraction_count": len(extractions),
        "lx_entity_classes": ", ".join(sorted(classes)),
        "lx_organizations": ", ".join(_dedupe_preserve_order(organizations)),
        "lx_people": ", ".join(_dedupe_preserve_order(people)),
        "lx_deal_terms": ", ".join(_dedupe_preserve_order(terms)),
        "lx_money_mentions": money_mentions,
        "lx_date_mentions": date_mentions,
        "lx_has_earnout": any("earnout" in term for term in normalized_terms),
        "lx_has_escrow": any("escrow" in term for term in normalized_terms),
    }


def _langextract_examples(lx: Any) -> list[Any]:
    return [
        lx.data.ExampleData(
            text=(
                "TechCorp Industries will pay $45,000,000 in cash consideration, "
                "with a $1,500,000 escrow reserve and a $5,000,000 earnout to "
                "acquire StartupXYZ LLC. CTO Dr. Sarah Chen signed on January 15, 2025."
            ),
            extractions=[
                lx.data.Extraction(extraction_class="organization", extraction_text="TechCorp Industries"),
                lx.data.Extraction(extraction_class="organization", extraction_text="StartupXYZ LLC"),
                lx.data.Extraction(extraction_class="money", extraction_text="$45,000,000"),
                lx.data.Extraction(extraction_class="money", extraction_text="$1,500,000"),
                lx.data.Extraction(extraction_class="money", extraction_text="$5,000,000"),
                lx.data.Extraction(extraction_class="deal_term", extraction_text="cash consideration"),
                lx.data.Extraction(extraction_class="deal_term", extraction_text="escrow reserve"),
                lx.data.Extraction(extraction_class="deal_term", extraction_text="earnout"),
                lx.data.Extraction(extraction_class="person", extraction_text="Dr. Sarah Chen"),
                lx.data.Extraction(extraction_class="date", extraction_text="January 15, 2025"),
            ],
        )
    ]


def _dedupe_preserve_order(values: list[str], *, max_items: int = 16) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.strip()
        if not key:
            continue
        lower = key.lower()
        if lower in seen:
            continue
        seen.add(lower)
        deduped.append(key)
        if len(deduped) >= max_items:
            break
    return deduped


def _safe_int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else minimum
