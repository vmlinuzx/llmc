import pytest
from pathlib import Path
import sqlite3
import struct
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
from llmc.te.config import get_te_config, TeConfig
from llmc.routing import router as routing_router

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


def test_routing_metrics_ingest(tmp_path, monkeypatch, caplog):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    
    # Create config that forces some fallbacks
    (repo_root / "llmc.toml").write_text("""
[tool_envelope]
telemetry_enabled = true
capture_output = false

[embeddings]
default_profile = "default_docs"

[embeddings.profiles.default_docs]
provider = "hash"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "embeddings"

# code route is missing for a slice_type='code' file, leading to fallback
[routing.slice_type_to_route]
code = "missing_code_route"
docs = "docs"
weird_type = "non_existent_profile_route"
""")
    
    # Create files
    (repo_root / "code.py").write_text("def foo(): pass") # Will fall back due to missing_code_route
    (repo_root / "doc.md").write_text("# Doc") # Should go to docs
    (repo_root / "config.weird").write_text("key=value") # Will fall back due to non_existent_profile_route
    
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("TE_AGENT_ID", "test-agent")
    
    # Enable telemetry by explicitly clearing the cache of get_te_config
    load_config.cache_clear()

    # Ensure log_routing_event is properly imported and functional during execution
    # index_repo triggers slice classification and hence get_route_for_slice_type
    index_repo() 
    
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    
    # execute_embeddings triggers resolve_route and logs routing_ingest_slice
    # It also logs fallbacks if the profile/index resolution fails
    # We capture logs to verify fallbacks occurred
    with caplog.at_level(logging.WARNING):
        execute_embeddings(db, repo_root)
        
    # Verify fallbacks via logs
    assert "Missing 'embeddings.routes.missing_code_route' for ingest. Falling back to 'docs' route." in caplog.text


def test_query_routing_fallback(tmp_path, monkeypatch, caplog, create_llmc_toml):
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
    load_config.cache_clear() # Clear TE config cache
    get_route_for_slice_type.cache_clear() # Clear rag config cache
    resolve_route.cache_clear() # Clear rag config cache

    # Setup dummy database with 'emb_docs' and 'embeddings' tables
    db_path = repo_root / ".rag" / "index_v2.db"
    db_path.parent.mkdir(exist_ok=True)
    db = Database(db_path)
    db.conn.execute("CREATE TABLE IF NOT EXISTS emb_docs (span_hash TEXT PRIMARY KEY, vec BLOB, route_name TEXT, profile_name TEXT)")
    
    # Insert dummy vector with correct size (64 floats * 4 bytes = 256 bytes)
    # Use a non-zero vector to avoid potential cosine similarity issues with zero vectors
    dummy_vec = struct.pack(f"<{64}f", *([0.1] * 64))
    db.conn.execute("INSERT INTO emb_docs (span_hash, vec, route_name, profile_name) VALUES (?, ?, ?, ?)", ("hash_doc", dummy_vec, "docs", "default_docs"))
    db.conn.commit()
    db.close()

    # Mock classify_query to always return "code" classification for a specific query
    # (router.Decision uses classify_query imported in llmc.routing.router)
    original_classify_query = routing_router.classify_query
    
    def mock_classify_query(query_text: str, tool_context: dict | None) -> dict:
        if "code snippet" in query_text:
            return {
                "route_name": "code",
                "confidence": 0.9,
                "reasons": ["code_heuristic_match"],
            }
        return original_classify_query(query_text, tool_context)
    
    monkeypatch.setattr(routing_router, "classify_query", mock_classify_query)

    # Mock embedding backend so the test does not depend on real embedding
    # configuration or external models.
    from tools.rag import search

    class MockBackend:
        def __init__(self, dim: int = 64) -> None:
            self._dim = dim

        def embed_queries(self, texts):
            return [[0.1] * self._dim for _ in texts]

        @property
        def model_name(self) -> str:
            return "mock-backend"

        @property
        def dim(self) -> int:
            return self._dim

    def mock_build_embedding_backend(model_name: str, dim: int) -> MockBackend:
        return MockBackend(dim)

    monkeypatch.setattr(search, "build_embedding_backend", mock_build_embedding_backend)

    query = "Find this code snippet"

    with caplog.at_level(logging.DEBUG):
        # The query should classify as "code", but fall back to "docs" because
        # [embeddings.routes.code] and [embeddings.profiles.code_jina] are missing.
        from tools.rag.search import search_spans
        results = search_spans(query, limit=1, repo_root=repo_root)
        
        # We don't assert len(results) because the vector search itself might fail in this
        # test environment (missing sqlite-vec), but we confirmed the routing logic above.

        # Verify debug logs for classification and fallback
        assert "Query routing classification: route='code' confidence=0.90 reasons=['code_heuristic_match']" in caplog.text
        assert "Config: Missing 'embeddings.routes.code' for query. Falling back to 'docs' route." in caplog.text
        assert "Embedding query for route='code' (profile='default_docs')" in caplog.text
