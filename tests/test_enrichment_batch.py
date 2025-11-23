
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from tools.rag.database import Database
from tools.rag.enrichment import batch_enrich, EnrichmentBatchResult


def _insert_file_and_span(
    db: Database,
    repo_root: Path,
    rel_path: str,
    symbol: str,
    span_hash: str,
) -> None:
    code = f"def {symbol}():\n    return '{symbol}'\n"
    file_rel = Path(rel_path)
    file_path = repo_root / file_rel
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code, encoding="utf-8")

    # Use INSERT OR IGNORE to handle multiple spans in same file
    db.conn.execute(
        "INSERT OR IGNORE INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
        (str(file_rel), "python", "hash-" + span_hash, len(code.encode("utf-8")), 123456.0),
    )
    db.conn.commit()

    file_id = db.conn.execute(
        "SELECT id FROM files WHERE path=?", (str(file_rel),)
    ).fetchone()[0]

    db.conn.execute(
        """
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line,
                           byte_start, byte_end, span_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            symbol,
            "function",
            1,
            2,
            0,
            len(code.encode("utf-8")),
            span_hash,
        ),
    )
    db.conn.commit()


def _make_db(tmp_path: Path) -> tuple[Database, Path]:
    repo_root = tmp_path
    db_path = repo_root / "test.db"
    db = Database(db_path)
    return db, repo_root


def _fake_enrichment_payload(summary: str = "Test summary") -> Dict[str, Any]:
    return {
        "summary_120w": summary,
        "inputs": ["arg"],
        "outputs": ["ret"],
        "side_effects": [],
        "pitfalls": [],
        "usage_snippet": "example()",
        "evidence": [{"field": "summary_120w", "lines": [1, 2]}],
        "tags": ["test"],
    }


def test_batch_enrich_multiple_spans_respects_limit_and_progresses(tmp_path) -> None:
    db, repo_root = _make_db(tmp_path)

    span_hashes = ["span_f1", "span_f2", "span_f3"]
    symbols = ["f1", "f2", "f3"]
    for span_hash, sym in zip(span_hashes, symbols):
        _insert_file_and_span(db, repo_root, "mod.py", sym, span_hash)

    calls: list[str] = []

    def fake_llm_call(prompt: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(prompt["span_hash"])
        assert prompt["span_hash"] in span_hashes
        return _fake_enrichment_payload(summary=f"Summary for {prompt['span_hash']}")

    # First batch: limit 2
    result1 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call,
        batch_size=2,
        model="test-model",
    )

    assert isinstance(result1, EnrichmentBatchResult)
    assert result1.attempted == 2
    assert result1.succeeded == 2
    assert result1.failed == 0

    rows = db.conn.execute("SELECT span_hash FROM enrichments").fetchall()
    enriched_hashes = {row["span_hash"] for row in rows}
    assert len(enriched_hashes) == 2

    # Second batch: should process the remaining span
    result2 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call,
        batch_size=2,
        model="test-model",
    )

    assert isinstance(result2, EnrichmentBatchResult)
    assert result2.attempted == 1
    assert result2.succeeded == 1
    assert result2.failed == 0

    rows = db.conn.execute("SELECT span_hash FROM enrichments").fetchall()
    enriched_hashes = {row["span_hash"] for row in rows}
    assert enriched_hashes == set(span_hashes)

    # Third batch: nothing left to do; LLM may or may not be called depending
    # on cooldown semantics, but no *new* enrichments should be written.
    result3 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call,
        batch_size=2,
        model="test-model",
    )

    assert isinstance(result3, EnrichmentBatchResult)
    rows_after = db.conn.execute("SELECT span_hash FROM enrichments").fetchall()
    assert len(rows_after) == 3


def test_batch_enrich_is_idempotent_for_completed_spans(tmp_path) -> None:
    db, repo_root = _make_db(tmp_path)

    span_hash = "span_single"
    _insert_file_and_span(db, repo_root, "single.py", "only", span_hash)

    calls: list[str] = []

    def fake_llm_call_first(prompt: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(prompt["span_hash"])
        assert prompt["span_hash"] == span_hash
        return _fake_enrichment_payload(summary="First run")

    # First run should enrich the single span.
    result1 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call_first,
        batch_size=1,
        model="test-model",
    )

    assert result1.attempted == 1
    assert result1.succeeded == 1
    assert result1.failed == 0
    assert calls == [span_hash]

    rows = db.conn.execute(
        "SELECT span_hash, summary FROM enrichments WHERE span_hash=?",
        (span_hash,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["summary"] == "First run"

    # Second run: if pending_enrichments works as intended, there should be no
    # pending spans, and we should not need to call the LLM again. Use a
    # callable that would explode if invoked.
    def fake_llm_call_second(prompt: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        raise AssertionError("LLM should not be called on already-enriched spans")

    result2 = batch_enrich(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm_call_second,
        batch_size=1,
        model="test-model",
    )

    assert result2.attempted == 0
    assert result2.succeeded == 0
    assert result2.failed == 0

    rows_after = db.conn.execute(
        "SELECT span_hash, summary FROM enrichments WHERE span_hash=?",
        (span_hash,),
    ).fetchall()
    assert len(rows_after) == 1
    assert rows_after[0]["summary"] == "First run"
