"""Phase 2 – Enriched schema graph integration tests.

These tests exercise `build_enriched_schema_graph` in isolation from the
CLI, using a tiny on-disk database and a synthetic repo with one file.
"""

from __future__ import annotations

from pathlib import Path

from llmc.rag.database import Database
from llmc.rag.schema import build_enriched_schema_graph


def _write_simple_module(repo_root: Path) -> Path:
    """Create a minimal Python module that defines foo.bar()."""
    repo_root.mkdir(parents=True, exist_ok=True)
    source_file = repo_root / "foo.py"
    source_file.write_text(
        "def bar():\n    return 42\n",
        encoding="utf-8",
    )
    return source_file


def _seed_index_with_matching_enrichment(db_path: Path) -> None:
    """Create a tiny index with one file/span/enrichment row.

    This mirrors the helper in test_enrichment_db_helpers but is kept
    local here so the tests remain independent.
    """
    db = Database(db_path)

    with db.transaction() as conn:
        # files.path is stored repo-relative ("foo.py")
        conn.execute(
            """
            INSERT INTO files(path, lang, file_hash, size, mtime)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("foo.py", "python", "hash", 10, 0.0),
        )
        file_id = conn.execute("SELECT id FROM files WHERE path = ?", ("foo.py",)).fetchone()[0]

        conn.execute(
            """
            INSERT INTO spans(
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, doc_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, "foo.bar", "function", 1, 5, 0, 10, "span1", None),
        )

        conn.execute(
            """
            INSERT INTO enrichments(
                span_hash, summary, tags, evidence, model,
                created_at, schema_ver, inputs, outputs,
                side_effects, pitfalls, usage_snippet
            ) VALUES (?, ?, ?, ?, ?, strftime('%s','now'), ?, ?, ?, ?, ?, ?)
            """,
            ("span1", "test summary", None, "[]", "test-model", "1", "[]", "[]", "[]", "[]", None),
        )

    db.close()


def _seed_index_without_matching_enrichment(db_path: Path) -> None:
    """Create index with a span but no matching enrichment row.

    This exercises the Phase 2 policy that missing enrichment is
    non-fatal and leaves entity.metadata untouched.
    """
    db = Database(db_path)

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO files(path, lang, file_hash, size, mtime)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("foo.py", "python", "hash", 10, 0.0),
        )
        file_id = conn.execute("SELECT id FROM files WHERE path = ?", ("foo.py",)).fetchone()[0]

        conn.execute(
            """
            INSERT INTO spans(
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, doc_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, "foo.bar", "function", 1, 5, 0, 10, "span1", None),
        )
        # NOTE: no corresponding row in enrichments

    db.close()


def test_build_enriched_schema_graph_attaches_enrichment(tmp_path: Path) -> None:
    """Happy path: matching span + enrichment attaches metadata to entity."""
    repo_root = tmp_path / "repo"
    source_file = _write_simple_module(repo_root)

    db_path = repo_root / ".rag" / "index_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_index_with_matching_enrichment(db_path)

    graph = build_enriched_schema_graph(
        repo_root=repo_root,
        db_path=db_path,
        file_paths=[source_file],
    )

    # Find the function entity for foo.bar
    func_entities = [e for e in graph.entities if e.id.startswith("sym:foo.bar")]
    assert func_entities, "Expected at least one entity for sym:foo.bar"
    entity = func_entities[0]

    # Enrichment fields should have been attached
    assert entity.metadata.get("summary") == "test summary"
    assert entity.metadata.get("span_hash") == "span1"


def test_build_enriched_schema_graph_missing_enrichment_is_graceful(tmp_path: Path) -> None:
    """When no enrichment exists for a span, integration is non-fatal.

    The graph should still be built, and the entity should not have any
    enrichment fields like summary/span_hash attached.
    """
    repo_root = tmp_path / "repo"
    source_file = _write_simple_module(repo_root)

    db_path = repo_root / ".rag" / "index_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_index_without_matching_enrichment(db_path)

    graph = build_enriched_schema_graph(
        repo_root=repo_root,
        db_path=db_path,
        file_paths=[source_file],
    )

    func_entities = [e for e in graph.entities if e.id.startswith("sym:foo.bar")]
    assert func_entities, "Expected at least one entity for sym:foo.bar"
    entity = func_entities[0]

    # Policy from Phase 2 (2C): missing enrichment is non-fatal and leaves
    # metadata untouched for enrichment-specific fields.
    assert "summary" not in entity.metadata
    assert "span_hash" not in entity.metadata
