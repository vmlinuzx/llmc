"""Integration tests for the LLMC enrichment pipeline.

These tests exercise the high-level enrichment entry points in
``tools.rag.enrichment`` against a real on-disk database, while using a
mock/stub LLM callable. They are intentionally lightweight and focused
on end-to-end behaviour:

- Pending spans are discovered via the planning layer.
- The LLM callable is invoked with a prompt payload for each span.
- Successful responses are validated and written into the DB.
- Failures are reported via the batch result and do not corrupt state.

Most of the lower-level details (schema validation, ignore rules,
cooldown behaviour, etc.) are already covered by the more targeted unit
tests in:

- tests/test_enrichment_batch.py
- tests/test_enrichment_cascade.py
- tests/test_enrichment_config.py
- tests/test_enrichment_spanhash_and_fallbacks.py

These integration tests focus on ensuring that the high-level wiring
remains correct as the enrichment pipeline evolves.

"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from tools.rag.database import Database
from tools.rag.enrichment import batch_enrich, EnrichmentBatchResult
from tools.rag.workers import enrichment_plan


def _insert_file_and_span(
    db: Database,
    repo_root: Path,
    rel_path: str,
    symbol: str,
    span_hash: str,
    code: str = "def foo():\n    return 42\n",
) -> None:
    """Helper to insert a single file + span into the test DB.

    This mirrors the patterns used in ``test_enrichment_batch.py`` but keeps
    the setup local to this module so the tests remain self-contained.
    """
    file_path = repo_root / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code, encoding="utf-8")

    db.conn.execute(
        """        INSERT INTO files (path, lang, file_hash, size, mtime)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(rel_path), "python", "hash-" + span_hash, len(code.encode("utf-8")), 123456.0),
    )
    db.conn.commit()

    file_id = db.conn.execute(
        "SELECT id FROM files WHERE path = ?", (str(rel_path),)
    ).fetchone()[0]

    db.conn.execute(
        """        INSERT INTO spans (
            file_id,
            symbol,
            kind,
            start_line,
            end_line,
            byte_start,
            byte_end,
            span_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            symbol,
            "function",
            1,
            10,
            0,
            len(code.encode("utf-8")),
            span_hash,
        ),
    )
    db.conn.commit()


def _make_db(tmp_path: Path) -> tuple[Database, Path]:
    """Create a fresh test database and repo root under ``tmp_path``."""
    repo_root = tmp_path
    db_path = repo_root / "test.db"
    db = Database(db_path)
    return db, repo_root


def _fake_llm_call_factory(summary_prefix: str = "Summary") -> callable:
    """Return a simple fake LLM callable that records calls and returns a payload.

    The callable returns a dict that matches the enrichment schema expectations
    used by ``execute_enrichment``.
    """

    calls: List[Dict[str, Any]] = []

    def _fake_llm_call(prompt: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(prompt)
        span_hash = prompt.get("span_hash", "unknown")
        return {
            "summary": f"{summary_prefix} for {span_hash}",
            "tags": ["test", "integration"],
            "inputs": "n/a",
            "outputs": "n/a",
            "side_effects": "none",
            "pitfalls": "",
            "usage_snippet": f"call_{span_hash}()",
            "schema_version": "v1",
        }

    # Attach the calls list for inspection in tests.
    _fake_llm_call.calls = calls  # type: ignore[attr-defined]
    return _fake_llm_call


def test_single_span_enrichment_integration(tmp_path: Path) -> None:
    """End-to-end: one span is planned, enriched, and written to the DB."""
    db, repo_root = _make_db(tmp_path)
    span_hash = "span_single"
    _insert_file_and_span(db, repo_root, Path("foo.py"), "foo", span_hash)

    fake_llm = _fake_llm_call_factory("Single-span summary")

    # Sanity: ensure there is exactly one pending item in the plan.
    plan = enrichment_plan(db, repo_root, limit=10, cooldown_seconds=0)
    assert len(plan) == 1
    assert plan[0]["span_hash"] == span_hash

    result = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm,
        batch_size=4,
        model="test-model",
        cooldown_seconds=0,
    )

    assert isinstance(result, EnrichmentBatchResult)
    assert result.attempted == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.errors == []

    # The LLM should have been called exactly once.
    assert len(fake_llm.calls) == 1  # type: ignore[attr-defined]
    assert fake_llm.calls[0]["span_hash"] == span_hash  # type: ignore[attr-defined]

    # The enrichment row should be present in the DB.
    row = db.conn.execute(
        "SELECT span_hash, summary, tags, usage_snippet FROM enrichments WHERE span_hash=?",
        (span_hash,),
    ).fetchone()
    assert row is not None
    assert row["span_hash"] == span_hash
    assert "Single-span summary" in row["summary"]
    assert "integration" in row["tags"]


def test_multiple_spans_batch_integration(tmp_path: Path) -> None:
    """End-to-end: multiple spans are enriched across one or more batches."""
    db, repo_root = _make_db(tmp_path)
    span_hashes = [f"span_{i}" for i in range(5)]
    for i, span_hash in enumerate(span_hashes):
        _insert_file_and_span(
            db,
            repo_root,
            Path(f"file{i}.py"),
            f"func_{i}",
            span_hash,
        )

    fake_llm = _fake_llm_call_factory("Batch summary")

    # First batch should process up to batch_size spans.
    result1 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm,
        batch_size=3,
        model="test-model",
        cooldown_seconds=0,
    )

    assert isinstance(result1, EnrichmentBatchResult)
    assert result1.attempted == 3
    assert result1.succeeded == 3
    assert result1.failed == 0

    # Second batch should process the remaining spans.
    result2 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm,
        batch_size=3,
        model="test-model",
        cooldown_seconds=0,
    )

    assert isinstance(result2, EnrichmentBatchResult)
    assert result2.attempted == 2
    assert result2.succeeded == 2
    assert result2.failed == 0

    # Third batch should find nothing left to enrich.
    result3 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm,
        batch_size=3,
        model="test-model",
        cooldown_seconds=0,
    )

    assert isinstance(result3, EnrichmentBatchResult)
    assert result3.attempted == 0
    assert result3.succeeded == 0
    assert result3.failed == 0

    # All span hashes should now have enrichment rows.
    rows = db.conn.execute(
        "SELECT span_hash FROM enrichments ORDER BY span_hash"
    ).fetchall()
    enriched = [row["span_hash"] for row in rows]
    assert enriched == sorted(span_hashes)


def test_enrichment_errors_are_reported_and_do_not_write_rows(tmp_path: Path) -> None:
    """If the LLM callable fails, errors are reported and no rows are written.

    This ensures that the pipeline handles LLM-level failures gracefully
    without corrupting the enrichment table.
    """
    db, repo_root = _make_db(tmp_path)
    span_hash = "span_error"
    _insert_file_and_span(db, repo_root, Path("err.py"), "err_func", span_hash)

    calls: List[Dict[str, Any]] = []

    def failing_llm(prompt: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(prompt)
        raise RuntimeError("synthetic LLM failure")

    result = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=failing_llm,
        batch_size=4,
        model="test-model",
        cooldown_seconds=0,
    )

    assert isinstance(result, EnrichmentBatchResult)
    assert result.attempted == 1
    assert result.succeeded == 0
    assert result.failed == 1
    assert len(result.errors) == 1
    assert "synthetic LLM failure" in result.errors[0]

    # The LLM should have been called at least once.
    assert len(calls) == 1

    # No enrichment rows should be written for the failed span.
    row = db.conn.execute(
        "SELECT span_hash FROM enrichments WHERE span_hash=?",
        (span_hash,),
    ).fetchone()
    assert row is None
