from __future__ import annotations

from pathlib import Path
from typing import Any

from llmc.rag.database import Database
from llmc.rag.workers import execute_enrichment


def _insert_file_and_span(
    db: Database,
    repo_root: Path,
    rel_path: str,
    span_hash: str,
    code: str = "def foo():\n    return 42\n",
) -> None:
    """Minimal helper to insert a single file + span into the test DB."""
    file_path = repo_root / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code, encoding="utf-8")

    db.conn.execute(
        """
        INSERT INTO files (path, lang, file_hash, size, mtime)
        VALUES (?, ?, ?, ?, ?)
        """,
        (rel_path, "python", "hash-" + span_hash, len(code.encode("utf-8")), 123456.0),
    )
    db.conn.commit()

    file_id = db.conn.execute("SELECT id FROM files WHERE path = ?", (rel_path,)).fetchone()[0]

    db.conn.execute(
        """
        INSERT INTO spans (
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
            "func",
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
    repo_root = tmp_path
    db_path = repo_root / "test.db"
    db = Database(db_path)
    # Minimal llmc.toml with enrichment.path_weights so code-first scheduling has signal.
    (repo_root / "llmc.toml").write_text(
        """
[enrichment.path_weights]
"src/**"        = 1
"**/tests/**"   = 6
"docs/**"       = 8
"*.md"          = 7
""",
        encoding="utf-8",
    )
    return db, repo_root


def _fake_llm_call() -> callable:
    calls: list[dict[str, Any]] = []

    def _call(prompt: dict[str, Any]) -> dict[str, Any]:
        calls.append(prompt)
        span_hash = prompt.get("span_hash", "unknown")
        return {
            "summary_120w": f"Summary for {span_hash}",
            "tags": ["test"],
            "inputs": ["n/a"],
            "outputs": ["n/a"],
            "side_effects": [],
            "pitfalls": [],
            "usage_snippet": f"call_{span_hash}()",
            "evidence": [{"field": "summary_120w", "lines": [1, 10]}],
            "schema_version": "v1",
        }

    _call.calls = calls  # type: ignore[attr-defined]
    return _call


def test_execute_enrichment_respects_path_weights_when_code_first(tmp_path: Path) -> None:
    """execute_enrichment should process lower-weight (higher priority) paths first."""
    db, repo_root = _make_db(tmp_path)

    # Three spans in different paths; defaults in llmc.enrichment.config will assign:
    # - src/core/router.py -> weight 1
    # - src/tests/test_router.py -> weight 6
    # - docs/README.md -> weight 8
    router_hash = "span_router"
    test_hash = "span_test"
    docs_hash = "span_docs"

    _insert_file_and_span(db, repo_root, "src/core/router.py", router_hash)
    _insert_file_and_span(db, repo_root, "src/tests/test_router.py", test_hash)
    _insert_file_and_span(db, repo_root, "docs/README.md", docs_hash)

    fake_llm = _fake_llm_call()

    successes, errors = execute_enrichment(
        db=db,
        repo_root=repo_root,
        llm_call=fake_llm,
        limit=10,
        model="test-model",
        cooldown_seconds=0,
        code_first=True,
        starvation_ratio_high=5,
        starvation_ratio_low=1,
    )

    assert errors == []
    assert successes == 3

    called_hashes = [call["span_hash"] for call in fake_llm.calls]  # type: ignore[attr-defined]
    # Lower weight (higher priority) should be processed first.
    assert called_hashes[0] == router_hash
    assert called_hashes[1] == test_hash
    assert called_hashes[2] == docs_hash
