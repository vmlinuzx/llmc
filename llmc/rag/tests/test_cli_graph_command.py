import json
from pathlib import Path

from click.testing import CliRunner

from llmc.rag.cli import cli
from llmc.rag.database import Database


def _make_repo_with_single_function(tmp_path: Path) -> Path:
    """Create a tiny repo with a single Python function."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = repo_root / "foo.py"
    source.write_text(
        "def bar():\n    return 42\n",
        encoding="utf-8",
    )
    return repo_root


def _seed_index_with_matching_enrichment(repo_root: Path) -> Path:
    """Seed a minimal enrichment index that matches foo.bar in foo.py."""
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

        span_hash = "test-span-cli-graph"

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
                "cli summary",
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


def test_graph_cli_allows_ast_only_without_enrichment(
    tmp_path: Path, monkeypatch
) -> None:
    """`rag graph --allow-empty-enrichment` should succeed without a DB and produce a plain AST-only graph."""
    repo_root = _make_repo_with_single_function(tmp_path)
    runner = CliRunner()

    # Run CLI from inside the temp repo so _find_repo_root() picks it up.
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli, ["graph", "--allow-empty-enrichment"])
    assert result.exit_code == 0, result.output

    graph_file = repo_root / ".llmc" / "rag_graph.json"
    assert graph_file.exists(), "Graph JSON should be written by CLI in AST-only mode"

    data = json.loads(graph_file.read_text(encoding="utf-8"))
    assert "entities" in data, "Expected 'entities' key in graph JSON"
    assert isinstance(data["entities"], list)
    assert data["entities"], "Expected at least one entity in the graph"

    # With no enrichment rows in the DB, no entity should have a summary.
    for entity in data["entities"]:
        metadata = entity.get("metadata") or {}
        assert (
            "summary" not in metadata
        ), "Did not expect enrichment summaries in plain mode"


def test_graph_cli_require_enrichment_raises_on_empty_db(
    tmp_path: Path, monkeypatch
) -> None:
    """When require_enrichment=True and DB has 0 enrichments, CLI should fail."""
    repo_root = _make_repo_with_single_function(tmp_path)
    monkeypatch.chdir(repo_root)

    runner = CliRunner()
    result = runner.invoke(cli, ["graph"])

    # CLI wraps the RuntimeError from build_graph_for_repo and exits non-zero.
    assert result.exit_code != 0
    assert "database has 0 enrichments" in result.output
    assert "require_enrichment=True" in result.output


def test_graph_cli_writes_enriched_graph_when_db_present(
    tmp_path: Path, monkeypatch
) -> None:
    """`rag graph` should build an enriched graph when the DB has enrichments."""
    repo_root = _make_repo_with_single_function(tmp_path)
    _seed_index_with_matching_enrichment(repo_root)

    runner = CliRunner()
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli, ["graph"])
    assert result.exit_code == 0, result.output

    graph_file = repo_root / ".llmc" / "rag_graph.json"
    assert graph_file.exists(), "Graph JSON should be written by CLI"

    # Verify enriched metadata appears in the JSON artifact.
    import json

    data = json.loads(graph_file.read_text(encoding="utf-8"))
    assert "entities" in data, "Expected 'entities' key in graph JSON"

    enriched = [
        e
        for e in data["entities"]
        if e.get("id") == "sym:foo.bar" and "summary" in e.get("metadata", {})
    ]
    assert enriched, "Expected at least one enriched entity for sym:foo.bar"
