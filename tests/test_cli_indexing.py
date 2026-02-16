"""CLI tests for indexing and schema commands."""

from pathlib import Path

import fs_explorer.indexing.pipeline as pipeline_module
import fs_explorer.main as main_module
from typer.testing import CliRunner


def test_root_task_mode_remains_compatible(tmp_path: Path, monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_run_workflow(
        task: str,
        folder: str = ".",
        *,
        use_index: bool = False,
        db_path: str | None = None,
    ) -> None:
        called["task"] = task
        called["folder"] = folder
        called["use_index"] = use_index
        called["db_path"] = db_path

    monkeypatch.setattr(main_module, "run_workflow", fake_run_workflow)

    runner = CliRunner()
    result = runner.invoke(
        main_module.app,
        ["--task", "who is the CTO?", "--folder", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert called["task"] == "who is the CTO?"
    assert called["folder"] == str(tmp_path)
    assert called["use_index"] is False


def test_query_command_enables_index_mode(tmp_path: Path, monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_run_workflow(
        task: str,
        folder: str = ".",
        *,
        use_index: bool = False,
        db_path: str | None = None,
    ) -> None:
        called["task"] = task
        called["folder"] = folder
        called["use_index"] = use_index
        called["db_path"] = db_path

    monkeypatch.setattr(main_module, "run_workflow", fake_run_workflow)

    runner = CliRunner()
    result = runner.invoke(
        main_module.app,
        ["query", "--task", "purchase price?", "--folder", str(tmp_path), "--db-path", "tmp.duckdb"],
    )

    assert result.exit_code == 0
    assert called["task"] == "purchase price?"
    assert called["folder"] == str(tmp_path)
    assert called["use_index"] is True
    assert called["db_path"] == "tmp.duckdb"


def test_index_and_schema_commands(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "agreement.md").write_text("Purchase price is $10.")
    (corpus / "risk_report.md").write_text("Risk summary here.")

    # Replace Docling path with plain text read for this unit test.
    monkeypatch.setattr(
        pipeline_module,
        "parse_file",
        lambda file_path: Path(file_path).read_text(),
    )

    db_path = tmp_path / "index.duckdb"
    runner = CliRunner()

    index_result = runner.invoke(
        main_module.app,
        ["index", str(corpus), "--db-path", str(db_path), "--discover-schema"],
    )
    assert index_result.exit_code == 0
    assert "Index Complete" in index_result.stdout

    show_result = runner.invoke(
        main_module.app,
        ["schema", "show", str(corpus), "--db-path", str(db_path)],
    )
    assert show_result.exit_code == 0
    assert "auto_corpus" in show_result.stdout
