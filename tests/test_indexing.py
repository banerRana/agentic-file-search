"""Tests for indexing and schema components."""

from pathlib import Path

import fs_explorer.indexing.pipeline as pipeline_module
from fs_explorer.indexing.chunker import SmartChunker
from fs_explorer.indexing.pipeline import IndexingPipeline
from fs_explorer.indexing.schema import SchemaDiscovery
from fs_explorer.storage import DuckDBStorage


def test_smart_chunker_overlap() -> None:
    text = "A" * 2500
    chunker = SmartChunker(chunk_size=1000, overlap=100)

    chunks = chunker.chunk_text(text)

    assert len(chunks) == 3
    assert chunks[1].start_char == chunks[0].end_char - 100
    assert chunks[2].start_char == chunks[1].end_char - 100


def test_schema_discovery_from_folder(tmp_path: Path) -> None:
    folder = tmp_path / "corpus"
    folder.mkdir()
    (folder / "01_master_agreement.md").write_text("# agreement\nprice: $10")
    (folder / "04_risk_report.md").write_text("# report\nrisk summary")

    schema = SchemaDiscovery().discover_from_folder(str(folder))

    fields = schema["fields"]
    field_names = {field["name"] for field in fields}
    assert "document_type" in field_names
    assert "mentions_currency" in field_names

    document_type_field = next(field for field in fields if field["name"] == "document_type")
    assert "agreement" in document_type_field["enum"]
    assert "report" in document_type_field["enum"]


def test_indexing_pipeline_indexes_and_marks_deleted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    corpus = tmp_path / "docs"
    corpus.mkdir()
    first = corpus / "a_agreement.md"
    second = corpus / "b_schedule.md"
    first.write_text("Purchase price is $45,000,000.\n\nSection 1.2")
    second.write_text("Schedule details.\n\nEffective Date: January 1, 2026")

    # Avoid Docling in this unit test; treat markdown as plain text.
    monkeypatch.setattr(
        pipeline_module,
        "parse_file",
        lambda file_path: Path(file_path).read_text(),
    )

    db_path = tmp_path / "index.duckdb"
    storage = DuckDBStorage(str(db_path))
    pipeline = IndexingPipeline(storage=storage)

    first_result = pipeline.index_folder(str(corpus), discover_schema=True)
    assert first_result.indexed_files == 2
    assert first_result.skipped_files == 0
    assert first_result.active_documents == 2
    assert first_result.schema_used is not None
    assert storage.count_chunks(corpus_id=first_result.corpus_id) > 0

    second.unlink()

    second_result = pipeline.index_folder(str(corpus))
    assert second_result.indexed_files == 1
    assert second_result.active_documents == 1

    all_docs = storage.list_documents(
        corpus_id=first_result.corpus_id,
        include_deleted=True,
    )
    deleted_paths = {doc["relative_path"] for doc in all_docs if doc["is_deleted"]}
    assert "b_schedule.md" in deleted_paths
