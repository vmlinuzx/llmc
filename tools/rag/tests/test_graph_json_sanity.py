from pathlib import Path

from tools.rag.schema import build_graph_for_repo
from tools.rag.database import Database


def _make_repo_with_single_function(tmp_path: Path) -> Path:
    """Create a tiny repo with a single Python function."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = repo_root / "foo.py"
    source.write_text(
        "def bar():\n"
        "    return 42\n",
        encoding="utf-8",
    )
    return repo_root


def _seed_enrichment_db_for_foo_bar(repo_root: Path) -> Path:
    """Seed a minimal enrichment DB for symbol foo.bar in foo.py."""
    source = repo_root / "foo.py"
    source_text = source.read_text(encoding="utf-8")

    db_path = repo_root / ".rag" / "index_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

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

        span_hash = "test-span-graph-sanity"

        # Insert span row for symbol "foo.bar" which the AST extractor will emit.
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

        # Insert matching enrichment row with a simple summary.
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
                "sanity summary",
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

    return db_path


def test_graph_json_enriched_entity_count_matches_db(tmp_path: Path) -> None:
    """Enriched entity count in graph should not exceed enrichment rows in DB."""
    repo_root = _make_repo_with_single_function(tmp_path)
    db_path = _seed_enrichment_db_for_foo_bar(repo_root)

    graph = build_graph_for_repo(repo_root, require_enrichment=True, db_path=db_path)

    # Count enrichment rows in DB.
    db = Database(db_path)
    try:
        conn = db.conn
        (enrich_count,) = conn.execute(
            "SELECT COUNT(*) FROM enrichments"
        ).fetchone()
    finally:
        db.close()

    enriched_entities = [
        e for e in graph.entities
        if "summary" in (e.metadata or {})
    ]

    assert enriched_entities, "Expected at least one enriched entity in graph"
    assert len(enriched_entities) <= enrich_count


def test_graph_json_enriched_entities_have_consistent_locations(tmp_path: Path) -> None:
    """Enriched entities in the graph should have sane location fields."""
    repo_root = _make_repo_with_single_function(tmp_path)
    db_path = _seed_enrichment_db_for_foo_bar(repo_root)

    graph = build_graph_for_repo(repo_root, require_enrichment=True, db_path=db_path)

    enriched_entities = [
        e for e in graph.entities
        if "summary" in (e.metadata or {})
    ]
    assert enriched_entities, "Expected at least one enriched entity in graph"

    for entity in enriched_entities:
        # file_path should be a non-empty string, usually repo-relative.
        assert isinstance(entity.file_path, str) and entity.file_path, (
            f"Expected non-empty file_path for enriched entity {entity.id}"
        )

        # start_line and end_line should be integers with start <= end.
        assert isinstance(entity.start_line, int), "Expected int start_line"
        assert isinstance(entity.end_line, int), "Expected int end_line"
        assert entity.start_line >= 1
        assert entity.start_line <= entity.end_line

