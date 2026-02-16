"""Tests for search filtering and merged retrieval ranking."""

from __future__ import annotations

import time
from pathlib import Path

import fs_explorer.indexing.pipeline as pipeline_module
import pytest

from fs_explorer.indexing.pipeline import IndexingPipeline
from fs_explorer.search import (
    IndexedQueryEngine,
    MetadataFilterParseError,
    parse_metadata_filters,
)
from fs_explorer.storage import DuckDBStorage


def test_parse_metadata_filters_supports_scalar_and_list_values() -> None:
    parsed = parse_metadata_filters(
        "document_type=agreement and mentions_currency=true, file_size_bytes>=100, "
        "document_type in (agreement, report)"
    )

    assert len(parsed) == 4
    assert parsed[0].field == "document_type"
    assert parsed[0].operator == "eq"
    assert parsed[0].value == "agreement"
    assert parsed[1].field == "mentions_currency"
    assert parsed[1].value is True
    assert parsed[2].operator == "gte"
    assert parsed[2].value == 100
    assert parsed[3].operator == "in"
    assert parsed[3].value == ["agreement", "report"]


def test_parse_metadata_filters_rejects_unknown_schema_fields() -> None:
    with pytest.raises(MetadataFilterParseError):
        parse_metadata_filters(
            "owner=finance",
            allowed_fields={"document_type", "mentions_currency"},
        )


def test_indexed_query_engine_unions_semantic_and_metadata_results(
    tmp_path: Path,
    monkeypatch,
) -> None:
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "a_agreement.md").write_text("Purchase price is $45,000,000.")
    (corpus / "b_report.md").write_text("Risk register and litigation exposure summary.")

    monkeypatch.setattr(
        pipeline_module,
        "parse_file",
        lambda file_path: Path(file_path).read_text(),
    )

    db_path = tmp_path / "index.duckdb"
    storage = DuckDBStorage(str(db_path))
    result = IndexingPipeline(storage=storage).index_folder(str(corpus), discover_schema=True)
    engine = IndexedQueryEngine(storage)

    hits = engine.search(
        corpus_id=result.corpus_id,
        query="purchase price",
        filters="document_type=report",
        limit=5,
    )

    by_path = {hit.relative_path: hit for hit in hits}
    assert "a_agreement.md" in by_path
    assert "b_report.md" in by_path
    assert by_path["a_agreement.md"].semantic_score > 0
    assert by_path["b_report.md"].metadata_score > 0


class _SlowStorage:
    def search_chunks(self, *, corpus_id: str, query: str, limit: int = 5):  # noqa: ARG002
        time.sleep(0.3)
        return [
            {
                "doc_id": "doc_semantic",
                "relative_path": "a.md",
                "absolute_path": "/tmp/a.md",
                "position": 0,
                "text": "semantic hit",
                "score": 3,
            }
        ]

    def search_documents_by_metadata(self, *, corpus_id: str, filters, limit: int = 20):  # noqa: ARG002
        time.sleep(0.3)
        return [
            {
                "doc_id": "doc_metadata",
                "relative_path": "b.md",
                "absolute_path": "/tmp/b.md",
                "preview_text": "metadata hit",
                "metadata_score": 1,
            }
        ]

    def get_active_schema(self, *, corpus_id: str):  # noqa: ARG002
        return None


def test_indexed_query_engine_executes_semantic_and_metadata_in_parallel() -> None:
    engine = IndexedQueryEngine(_SlowStorage())

    start = time.perf_counter()
    hits = engine.search(
        corpus_id="corpus_test",
        query="test",
        filters="document_type=agreement",
        limit=5,
    )
    elapsed = time.perf_counter() - start

    assert elapsed < 0.58
    assert {hit.doc_id for hit in hits} == {"doc_semantic", "doc_metadata"}
