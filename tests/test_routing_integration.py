import pytest
from pathlib import Path
import sqlite3
from tools.rag.indexer import index_repo
from tools.rag.database import Database
from tools.rag.workers import execute_embeddings, execute_enrichment
from tools.rag.types import SpanRecord
from tools.rag.config import (
    get_route_for_slice_type,
    resolve_route,
    ConfigError,
    load_config,
    is_query_routing_enabled,
)
import logging
from llmc.te.cli import _handle_stats # Added import for metrics testing
from llmc.te.config import get_te_config, TeConfig # Added import for telemetry config

@pytest.fixture
def create_llmc_toml(tmp_path):
    """Fixture to create and return the path to a test llmc.toml."""
    def _creator(content: str):
        repo_root = tmp_path / "repo"
        repo_root.mkdir(exist_ok=True)
        (repo_root / ".git").mkdir(exist_ok=True) # ensure .git exists for _find_repo_root
        config_path = repo_root / "llmc.toml"
        config_path.write_text(content)
        return repo_root, config_path
    return _creator


def test_routing_integration(tmp_path, monkeypatch):
    # Setup repo
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    
    # Create files
    (repo_root / "code.py").write_text("def foo(): pass")
    (repo_root / "doc.md").write_text("# Doc")
    
    # Config
    (repo_root / "llmc.toml").write_text("""
[embeddings]
default_profile = "docs"

[embeddings.profiles.code_jina]
provider = "ignored"
model = "hash-emb-v1"
dim = 64
capabilities = ["code"]

[embeddings.profiles.docs]
provider = "ignored"
model = "hash-emb-v1"
dim = 64

[embeddings.routes.code]
profile = "code_jina"
index = "emb_code"

[embeddings.routes.docs]
profile = "docs"
index = "embeddings"

[routing.slice_type_to_route]
code = "code"
docs = "docs"
""")
    
    monkeypatch.chdir(repo_root)
    
    # Index
    index_repo()
    
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    
    # Check spans classification
    row_code = db.conn.execute("SELECT slice_type, slice_language FROM spans WHERE file_id = (SELECT id FROM files WHERE path='code.py')").fetchone()
    assert row_code["slice_type"] == "code"
    assert row_code["slice_language"] == "python"
    
    row_doc = db.conn.execute("SELECT slice_type FROM spans WHERE file_id = (SELECT id FROM files WHERE path='doc.md')").fetchone()
    assert row_doc["slice_type"] == "docs"

    # Embeddings
    execute_embeddings(db, repo_root)
    
    # Check where embeddings went
    # Code -> emb_code
    code_emb = db.conn.execute("SELECT * FROM emb_code").fetchall()
    assert len(code_emb) > 0
    assert code_emb[0]["route_name"] == "code"
    assert code_emb[0]["profile_name"] == "code_jina"
    
    # Docs -> embeddings
    docs_emb = db.conn.execute("SELECT * FROM embeddings").fetchall()
    assert len(docs_emb) > 0
    assert docs_emb[0]["route_name"] == "docs"
    
    # Enrichment
    def mock_llm(prompt):
        return {
             "summary_120w": "summary",
             "inputs": [],
             "outputs": [],
             "side_effects": [],
             "pitfalls": [],
             "usage_snippet": None,
             "evidence": [],
             "tags": []
        }
        
    execute_enrichment(db, repo_root, mock_llm)
    
    # Check enrichment metadata
    # Filter by span hash from code file (using spans table to join or select)
    code_span_hash = code_emb[0]["span_hash"]
    enrich_code = db.conn.execute("SELECT content_type, content_language FROM enrichments WHERE span_hash = ?", (code_span_hash,)).fetchone()
    
    assert enrich_code["content_type"] == "code"
    assert enrich_code["content_language"] == "python"

def test_get_route_for_slice_type_missing_entry(create_llmc_toml, caplog):
    repo_root, _ = create_llmc_toml("""
[routing.slice_type_to_route]
code = "code"
# "docs" is intentionally missing for "weird_type"
""")
    # Clear cache to ensure fresh config load
    get_route_for_slice_type.cache_clear()
    
    with caplog.at_level(logging.WARNING):
        route = get_route_for_slice_type("weird_type", repo_root)
        assert route == "docs"
        assert "Missing 'routing.slice_type_to_route' entry for slice_type='weird_type'. Defaulting to route_name='docs'." in caplog.text
        # Ensure that the ConfigWarningFilter works by not logging twice
        get_route_for_slice_type("weird_type", repo_root)
        assert caplog.text.count("Missing 'routing.slice_type_to_route'") == 1

def test_resolve_route_missing_route_config_fallback(create_llmc_toml, caplog):
    repo_root, _ = create_llmc_toml("""
[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "emb_docs"

# embeddings.routes.code is intentionally missing
""")
    # Clear cache to ensure fresh config load
    resolve_route.cache_clear()
    
    with caplog.at_level(logging.WARNING):
        profile, index = resolve_route("code", "query", repo_root)
        assert profile == "default_docs"
        assert index == "emb_docs"
        assert "Missing 'embeddings.routes.code' for query. Falling back to 'docs' route." in caplog.text
        # Ensure that the ConfigWarningFilter works
        profile, index = resolve_route("code", "query", repo_root)
        assert caplog.text.count("Missing 'embeddings.routes.code'") == 1


def test_resolve_route_critical_missing_docs_route(create_llmc_toml):
    repo_root, _ = create_llmc_toml("""
# embeddings.routes.docs is intentionally missing
""")
    # Clear cache to ensure fresh config load
    resolve_route.cache_clear()

    with pytest.raises(ConfigError) as excinfo:
        resolve_route("docs", "query", repo_root)
    assert "Critical Config Error: 'embeddings.routes.docs' is missing" in str(excinfo.value)


def test_resolve_route_incomplete_route_definition_fallback(create_llmc_toml, caplog):
    repo_root, _ = create_llmc_toml("""
[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "emb_docs"

[embeddings.routes.code]
profile = "code_jina" # Index is missing
""")
    # Clear cache to ensure fresh config load
    resolve_route.cache_clear()

    with caplog.at_level(logging.WARNING):
        profile, index = resolve_route("code", "query", repo_root)
        assert profile == "default_docs"
        assert index == "emb_docs"
        assert "Route 'code' for query has incomplete definition (profile: code_jina, index: None). Falling back to 'docs' route." in caplog.text
        # Ensure that the ConfigWarningFilter works
        profile, index = resolve_route("code", "query", repo_root)
        assert caplog.text.count("Route 'code' for query has incomplete definition") == 1


def test_resolve_route_critical_missing_profile_non_docs_route(create_llmc_toml):
    repo_root, _ = create_llmc_toml("""
[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "emb_docs"

[embeddings.routes.code]
profile = "missing_profile" # This profile does not exist
index = "emb_code"
""")
    # Clear cache to ensure fresh config load
    resolve_route.cache_clear()

    with pytest.raises(ConfigError) as excinfo:
        resolve_route("code", "ingest", repo_root)
    assert "Config Error: Route 'code' for ingest refers to missing profile 'missing_profile'" in str(excinfo.value)


def test_routing_metrics_ingest(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    
    # Create config that forces some fallbacks
    (repo_root / "llmc.toml").write_text("""
[tool_envelope]
telemetry_enabled = true
capture_output = false

[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "emb_docs"

# code route is missing for a slice_type='code' file, leading to fallback
[routing.slice_type_to_route]
code = "missing_code_route" # This route is not defined
docs = "docs"
weird_type = "non_existent_profile_route" # This route also points to a missing profile config
""")
    
    # Create files
    (repo_root / "code.py").write_text("def foo(): pass") # Will fall back due to missing_code_route
    (repo_root / "doc.md").write_text("# Doc") # Should go to docs
    (repo_root / "config.weird").write_text("key=value") # Will fall back due to non_existent_profile_route
    
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("TE_AGENT_ID", "test-agent")
    
    # Enable telemetry by explicitly clearing the cache of get_te_config
    get_te_config.cache_clear()

    # Ensure log_routing_event is properly imported and functional during execution
    # index_repo triggers slice classification and hence get_route_for_slice_type
    index_repo() 
    
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    
    # execute_embeddings triggers resolve_route and logs routing_ingest_slice
    # It also logs fallbacks if the profile/index resolution fails
    execute_embeddings(db, repo_root)

    # Capture stdout of _handle_stats
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        _handle_stats(repo_root)
    output = f.getvalue()
    
    # Assert routing stats
    assert "Slices Ingested:" in output
    assert "by_slice_type:" in output
    assert "code           1" in output # code.py classified as code
    assert "docs           1" in output # doc.md classified as docs
    # "config.weird" classified as 'other' by default in classify_slice
    assert "other          1" in output 

    assert "by_route_name:" in output
    # code.py: classified as 'code', mapped to 'missing_code_route', which falls back to 'docs' route.
    # doc.md: classified as 'docs', mapped to 'docs' route.
    # config.weird: classified as 'other', mapped to 'non_existent_profile_route', which falls back to 'docs' route.
    assert "docs           3" in output 
    
    assert "Query Routing:" in output
    assert "Fallbacks:" in output
    # From missing_code_route mapping to docs (slice_type='code')
    assert "missing_route_config     1" in output
    # From non_existent_profile_route (slice_type='other')
    assert "missing_route_config     1" in output
    # From the execute_embeddings, the 'non_existent_profile_route' will eventually try to resolve the profile,
    # which will be missing, causing a fallback for profile.
    assert "missing_profile_reference     1" in output

    assert "Errors:" in output
    # No critical errors expected in this specific scenario as fallbacks handle it.
    assert "critical_missing_docs_route" not in output
    assert "critical_incomplete_docs_route" not in output
    assert "critical_missing_profile_and_default" not in output


def test_query_routing_fallback(tmp_path, monkeypatch, caplog):
    repo_root, _ = create_llmc_toml("""
[tool_envelope]
telemetry_enabled = true
capture_output = false

[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "emb_docs"

[routing.options]
enable_query_routing = true

# Intentionally omit [embeddings.routes.code] and [embeddings.profiles.code_jina]
# to force fallback for code-classified queries.
""")
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("TE_AGENT_ID", "test-agent")
    get_te_config.cache_clear() # Clear TE config cache
    get_route_for_slice_type.cache_clear() # Clear rag config cache
    resolve_route.cache_clear() # Clear rag config cache
    load_config.cache_clear() # Clear rag config cache
    is_query_routing_enabled.cache_clear() # Clear rag config cache

    # Setup dummy database with 'emb_docs' and 'embeddings' tables
    db_path = repo_root / ".rag" / "index_v2.db"
    db_path.parent.mkdir(exist_ok=True)
    db = Database(db_path)
    db.init_tables() # Create default tables
    db.conn.execute("CREATE TABLE IF NOT EXISTS emb_docs (span_hash TEXT PRIMARY KEY, vec BLOB, route_name TEXT, profile_name TEXT)")
    db.conn.execute("INSERT INTO emb_docs (span_hash, vec, route_name, profile_name) VALUES (?, ?, ?, ?)", ("hash_doc", b'\x00'*64, "docs", "default_docs"))
    db.conn.commit()
    db.close()

    # Mock classify_query to always return "code" classification for a specific query
    # (assuming classify_query is imported as llmc.routing.query_type.classify_query)
    from llmc.routing.query_type import classify_query
    original_classify_query = classify_query
    
    def mock_classify_query(query_text: str, tool_context: dict | None) -> dict:
        if "code snippet" in query_text:
            return {
                "route_name": "code",
                "confidence": 0.9,
                "reasons": ["code_heuristic_match"],
            }
        return original_classify_query(query_text, tool_context)
    
    monkeypatch.setattr("llmc.routing.query_type.classify_query", mock_classify_query)

    query = "Find this code snippet"

    with caplog.at_level(logging.DEBUG):
        # The query should classify as "code", but fall back to "docs" because
        # [embeddings.routes.code] and [embeddings.profiles.code_jina] are missing.
        from tools.rag.search import search_spans
        results = search_spans(query, limit=1, repo_root=repo_root)
        
        assert len(results) == 1
        assert results[0].span_hash == "hash_doc" # Should retrieve from docs index

        # Verify debug logs for classification and fallback
        assert "Query routing classification: route='code' confidence=0.90 reasons=['code_heuristic_match']" in caplog.text
        assert "Query routing: Classified route 'code' cannot be resolved safely" in caplog.text
        assert "Falling back to 'docs' route." in caplog.text
        assert "Query routing fallback resolved: route='docs', profile='default_docs', index='emb_docs'" in caplog.text

        # Verify telemetry event for fallback
        import sqlite3
        db_path = repo_root / ".llmc" / "te_telemetry.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT cmd FROM telemetry_events WHERE mode='routing_fallback'")
        fallback_events = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert any(
            "type=unsafe_classified_route_fallback,classified_route=code,reason=" in event and "fallback_to=docs" in event
            for event in fallback_events
        )


