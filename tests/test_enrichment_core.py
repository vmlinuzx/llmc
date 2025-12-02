
from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.rag.database import Database
from tools.rag.enrichment import EnrichmentBatchResult, batch_enrich


def _make_db_with_single_span(tmpdir: Path) -> tuple[Database, Path, str]:
    repo_root = tmpdir
    db_path = repo_root / "test.db"
    db = Database(db_path)

    # Create a simple Python file to back the span
    code = "def hello():\n    return 'world'\n"
    file_rel = Path("hello.py")
    file_path = repo_root / file_rel
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code, encoding="utf-8")

    # Insert file and span directly via SQL to avoid coupling to builders.
    db.conn.execute(
        "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
        (str(file_rel), "python", "hash123", len(code.encode("utf-8")), 123456.0),
    )
    db.conn.commit()

    file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (str(file_rel),)).fetchone()[0]

    span_hash = "span_hello"
    db.conn.execute(
        """
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (file_id, "hello", "function", 1, 2, 0, len(code.encode("utf-8")), span_hash),
    )
    db.conn.commit()

    return db, repo_root, span_hash


def test_batch_enrich_happy_path(tmp_path) -> None:
    db, repo_root, span_hash = _make_db_with_single_span(tmp_path)

    calls: dict[str, Any] = {}

    def fake_llm_call(prompt: dict[str, Any]) -> dict[str, Any]:
        # Record the prompt for basic sanity checks
        calls["prompt"] = prompt
        assert prompt["span_hash"] == span_hash
        assert prompt["path"].endswith("hello.py")
        assert prompt["lang"] == "python"
        assert prompt["lines"] == [1, 2]
        assert "code" in prompt
        assert "instructions" in prompt

        # Minimal payload that satisfies ENRICHMENT_SCHEMA in workers.py
        return {
            "summary_120w": "Test summary",
            "inputs": ["arg"],
            "outputs": ["ret"],
            "side_effects": [],
            "pitfalls": [],
            "usage_snippet": "hello()",
            "evidence": [{"field": "summary_120w", "lines": [1, 2]}],
            "tags": ["test"],
        }

    result = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call,
        batch_size=8,
        model="test-model",
    )

    assert isinstance(result, EnrichmentBatchResult)
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.attempted == 1

    # Verify enrichment row was written
    row = db.conn.execute(
        "SELECT summary, model, schema_ver, usage_snippet FROM enrichments WHERE span_hash=?",
        (span_hash,),
    ).fetchone()
    assert row is not None
    summary, model, schema_ver, usage_snippet = row
    assert summary == "Test summary"
    assert model == "test-model"
    assert schema_ver == "enrichment.v1"
    assert usage_snippet == "hello()"

    # Check that prompt was constructed as expected
    prompt = calls.get("prompt")
    assert prompt is not None
    assert prompt["span_hash"] == span_hash


def test_batch_enrich_no_pending_spans(tmp_path) -> None:
    repo_root = tmp_path
    db_path = repo_root / "test.db"
    db = Database(db_path)

    def fake_llm_call(prompt: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - should not be called
        raise AssertionError("LLM should not be called when there are no pending spans")

    result = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call,
        batch_size=4,
        model="test-model",
    )

    assert isinstance(result, EnrichmentBatchResult)
    assert result.attempted == 0
    assert result.succeeded == 0
    assert result.failed == 0
