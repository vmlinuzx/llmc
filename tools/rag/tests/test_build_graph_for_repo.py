
from pathlib import Path

import pytest

from tools.rag.schema import build_graph_for_repo
from tools.rag.database import Database


def _make_repo_with_single_function(tmp_path: Path) -> Path:
    """Create a tiny repo with a single Python function.

    Returns the repo_root path.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = repo_root / "foo.py"
    source.write_text(
        "def bar():\n"
        "    return 42\n"
    )
    return repo_root


def test_build_graph_for_repo_plain_mode_allows_empty_db(tmp_path: Path) -> None:
    """When require_enrichment=False, we should not hard-fail on empty DB.

    The graph builder still routes through build_enriched_schema_graph, but
    the orchestrator must not enforce any minimum enrichment coverage when
    require_enrichment is False.
    """
    repo_root = _make_repo_with_single_function(tmp_path)

    # No database or enrichments are created up front; Database() will create
    # an empty schema on demand.
    graph = build_graph_for_repo(repo_root, require_enrichment=False)

    # Basic sanity: we discovered at least one entity from foo.bar
    assert len(graph.entities) > 0

    # With an empty DB, no entities should have enrichment metadata attached.
    assert all("summary" not in e.metadata for e in graph.entities)


def test_build_graph_for_repo_require_enrichment_raises_on_empty_db(tmp_path: Path) -> None:
    """When require_enrichment=True and DB has 0 enrichments, raise.

    This encodes the Phase 2 guard-rail: if we *think* we are in enriched
    mode but the DB has no enrichment rows at all, it is almost certainly
    a pipeline/config error and should surface loudly.
    """
    repo_root = _make_repo_with_single_function(tmp_path)

    with pytest.raises(RuntimeError) as excinfo:
        build_graph_for_repo(repo_root, require_enrichment=True)

    msg = str(excinfo.value)
    assert "database has 0 enrichments" in msg
    assert "require_enrichment=True" in msg


def test_build_graph_for_repo_require_enrichment_succeeds_with_enrichment(tmp_path: Path) -> None:
    """Happy path: enrichment rows exist and at least one entity is enriched.

    This wires together:
    - _discover_source_files (repo_root -> foo.py)
    - build_schema_graph (entities for foo.bar)
    - Database.fetch_all_spans / fetch_all_enrichments
    - build_enriched_schema_graph (symbol + path matching)
    - build_graph_for_repo (require_enrichment=True gating)
    """
    repo_root = _make_repo_with_single_function(tmp_path)
    source = repo_root / "foo.py"
    source_text = source.read_text()

    # Seed a minimal, but structurally valid, enrichment DB that matches foo.bar
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    try:
        conn = db.conn

        # Insert file row with repo-relative path so matching logic sees "foo.py"
        conn.execute(
            """
            INSERT INTO files(path, lang, file_hash, size, mtime)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "foo.py",
                "python",
                "dummy-hash",
                len(source_text.encode("utf-8")),
                1234567890.0,
            ),
        )
        file_id = conn.execute(
            "SELECT id FROM files WHERE path = ?",
            ("foo.py",),
        ).fetchone()[0]

        span_hash = "test-span-123"

        # Insert span row for symbol "foo.bar" which the AST extractor will emit
        conn.execute(
            """
            INSERT INTO spans(
                file_id,
                symbol,
                kind,
                start_line,
                end_line,
                byte_start,
                byte_end,
                span_hash,
                doc_hint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                "foo.bar",
                "function",
                1,
                2,
                0,
                len(source_text.encode("utf-8")),
                span_hash,
                None,
            ),
        )

        # Insert matching enrichment row
        conn.execute(
            """
            INSERT INTO enrichments(
                span_hash,
                summary,
                tags,
                evidence,
                model,
                created_at,
                schema_ver,
                inputs,
                outputs,
                side_effects,
                pitfalls,
                usage_snippet
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_hash,
                "test summary",
                None,
                None,
                "test-model",
                "2025-01-01T00:00:00Z",
                "v1",
                None,
                None,
                None,
                None,
                None,
            ),
        )

        conn.commit()
    finally:
        db.close()

    graph = build_graph_for_repo(repo_root, require_enrichment=True, db_path=db_path)

    # At least one entity (foo.bar) should now have enrichment metadata attached.
    enriched = [e for e in graph.entities if e.metadata.get("summary") == "test summary"]
    assert enriched, "Expected at least one entity with attached enrichment summary"


def test_build_graph_for_repo_exports_enriched_metadata_to_json(tmp_path: Path) -> None:
    """Task 3C: Verify enriched metadata appears in .llmc/rag_graph.json export.

    This test ensures the full pipeline works:
    1. Build enriched graph from repo + DB
    2. Export to .llmc/rag_graph.json
    3. Verify enrichment metadata is present in the JSON file
    """
    repo_root = _make_repo_with_single_function(tmp_path)
    source = repo_root / "foo.py"
    source_text = source.read_text()

    # Create .llmc directory for the export
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()
    graph_json_path = llmc_dir / "rag_graph.json"

    # Seed enrichment DB with matching data
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    try:
        conn = db.conn

        # Insert file row
        conn.execute(
            "INSERT INTO files(path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
            ("foo.py", "python", "dummy-hash", len(source_text.encode("utf-8")), 1234567890.0),
        )
        file_id = conn.execute("SELECT id FROM files WHERE path = ?", ("foo.py",)).fetchone()[0]

        span_hash = "test-span-123"

        # Insert span row
        conn.execute(
            """
            INSERT INTO spans(file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash, doc_hint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, "foo.bar", "function", 1, 2, 0, len(source_text.encode("utf-8")), span_hash, None),
        )

        # Insert enrichment row with rich metadata
        conn.execute(
            """
            INSERT INTO enrichments(span_hash, summary, tags, evidence, model, created_at, schema_ver, inputs, outputs, side_effects, pitfalls, usage_snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_hash,
                "Returns the ultimate answer to life, the universe, and everything",
                '["math", "hitchhiker"]',
                '["42"]',
                "test-model",
                "2025-01-01T00:00:00Z",
                "v1",
                "[]",
                "[]",
                "None",
                "None",
                "result = bar()",
            ),
        )

        conn.commit()
    finally:
        db.close()

    # Build graph and export to JSON
    graph = build_graph_for_repo(repo_root, require_enrichment=True, db_path=db_path)
    graph.save(graph_json_path)

    # Load and verify the exported JSON
    import json

    with graph_json_path.open("r", encoding="utf-8") as f:
        graph_data = json.load(f)

    # Verify the graph structure
    assert "entities" in graph_data, "Expected 'entities' key in graph JSON"
    assert "relations" in graph_data, "Expected 'relations' key in graph JSON"

    # Find the foo.bar entity in the exported data
    foo_bar_entities = [
        e for e in graph_data["entities"] if e["id"] == "sym:foo.bar"
    ]
    assert len(foo_bar_entities) == 1, "Expected exactly one foo.bar entity in JSON"

    foo_bar = foo_bar_entities[0]

    # Verify enrichment metadata is present
    assert "metadata" in foo_bar, "Expected metadata field in entity"
    metadata = foo_bar["metadata"]

    assert "summary" in metadata, "Expected 'summary' in metadata"
    assert (
        metadata["summary"] == "Returns the ultimate answer to life, the universe, and everything"
    ), "Expected correct summary text"

    assert "tags" in metadata, "Expected 'tags' in metadata"
    assert metadata["tags"] == '["math", "hitchhiker"]', "Expected tags to be preserved"

    assert "usage_snippet" in metadata, "Expected 'usage_snippet' in metadata"
    assert metadata["usage_snippet"] == "result = bar()", "Expected usage snippet to be preserved"

    assert "evidence" in metadata, "Expected 'evidence' in metadata"
    assert metadata["evidence"] == ["42"], "Expected evidence list to be preserved"

    # Symbol and span_hash should be present for downstream tools
    assert metadata.get("symbol") == "foo.bar", "Expected symbol to be attached in metadata"
    assert metadata.get("span_hash") == span_hash, "Expected span_hash to be attached in metadata"

    # Location fields should be present at the entity level with repo-relative paths
    assert "file_path" in foo_bar, "Expected file_path on exported entity"
    assert foo_bar["file_path"] == "foo.py", "Expected repo-relative file_path in exported JSON"
    assert foo_bar["start_line"] == 1, "Expected correct start_line for foo.bar"
    assert foo_bar["end_line"] == 2, "Expected correct end_line for foo.bar"
