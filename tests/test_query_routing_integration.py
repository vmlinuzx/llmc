import struct

from tools.rag.database import Database
from tools.rag.search import search_spans


def create_dummy_embedding(val: float, dim: int = 64) -> bytes:
    vec = [val] * dim
    return struct.pack(f"<{dim}f", *vec)


def test_query_routing_integration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    # Config: Enable routing
    (repo_root / "llmc.toml").write_text("""
[embeddings.profiles.default_docs]
provider = "ignored"
model = "hash-emb-v1"
dim = 64

[embeddings.profiles.code_jina]
provider = "ignored"
model = "hash-emb-v1"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "embeddings"

[embeddings.routes.code]
profile = "code_jina"
index = "emb_code"

[routing.options]
enable_query_routing = true
""")

    monkeypatch.chdir(repo_root)

    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)

    # Insert files
    db.conn.execute(
        "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES ('doc.md', 'markdown', 'h1', 10, 0)"
    )
    db.conn.execute(
        "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES ('code.py', 'python', 'h2', 10, 0)"
    )

    file_id_doc = db.conn.execute("SELECT id FROM files WHERE path='doc.md'").fetchone()[0]
    file_id_code = db.conn.execute("SELECT id FROM files WHERE path='code.py'").fetchone()[0]

    # Insert spans
    db.conn.execute(f"""
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash, slice_type) 
        VALUES ({file_id_doc}, 'doc', 'text', 1, 1, 0, 10, 'hash_doc', 'docs')
    """)
    db.conn.execute(f"""
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash, slice_type) 
        VALUES ({file_id_code}, 'code', 'func', 1, 1, 0, 10, 'hash_code', 'code')
    """)

    # Insert embeddings:
    # Doc vector in 'embeddings' table
    # Code vector in 'emb_code' table
    # We use the same embedding backend (hash-emb-v1) for simplicity, so query vector will match both if we align values.
    # But to distinguish, we'll just check WHICH result comes back.
    # If I search for code, I should ONLY get hash_code.
    # If I search for doc, I should ONLY get hash_doc.

    vec_blob = create_dummy_embedding(
        0.1, 64
    )  # Value doesn't matter much with hash backend as it hashes the text

    # Actually, search_spans computes query vector using backend.embed_queries.
    # Hash backend is deterministic.
    # "def foo(): pass" -> vector V1
    # "how do I..." -> vector V2

    # To verify routing, we put 'hash_code' ONLY in emb_code, and 'hash_doc' ONLY in embeddings.
    # If we query a code string, routing selects emb_code, so we should find 'hash_code' (if vector matches somewhat)
    # OR at least we should NOT find 'hash_doc'.

    # Let's manually insert vectors that we know will match the query "close enough" or just rely on the fact that
    # we are partitioning the search space.

    # Insert random vectors
    db.conn.execute("INSERT INTO embeddings (span_hash, vec) VALUES ('hash_doc', ?)", (vec_blob,))
    db.conn.execute("INSERT INTO emb_code (span_hash, vec) VALUES ('hash_code', ?)", (vec_blob,))
    db.conn.commit()

    db.close()

    # 1. Test Code Query -> Should hit emb_code -> return hash_code (or nothing if no match), but DEFINITELY NOT hash_doc
    # Since we put the SAME vector in both, if we search emb_code we find hash_code. If we search embeddings we find hash_doc.
    # The hash-emb-v1 is sensitive to text, so our query vector won't perfectly match '0.1' everywhere.
    # BUT, cosine similarity with [0.1, 0.1...] and [0.1, 0.1...] is 1.0.
    # So if we generate a query, and 'hash_code' has vector X, and 'hash_doc' has vector X.
    # If we route to code, we find hash_code.

    # Re-open to inject exact matching vectors for a specific query
    # Let's pick a query "def code():"
    # We need to know what vector hash-emb-v1 produces for this?
    # Actually, we can just Mock the backend? No, `search_spans` calls `build_embedding_backend`.

    # Simpler approach:
    # Just use the stored vector [0.1...] for both.
    # Mock `build_embedding_backend` to return a backend that ALWAYS returns [0.1...] for any query.
    # This ensures dot product is perfect.

    from tools.rag import search

    class MockBackend:
        def embed_queries(self, texts):
            return [[0.1] * 64 for _ in texts]

        @property
        def model_name(self):
            return "mock"

        @property
        def dim(self):
            return 64

    def mock_build(*args, **kwargs):
        return MockBackend()

    monkeypatch.setattr(search, "build_embedding_backend", mock_build)

    # Test 1: Code Query
    # "def foo():" should be classified as code.
    results = search_spans("def foo():", repo_root=repo_root, debug=True)

    assert len(results) == 1
    assert results[0].span_hash == "hash_code"
    assert results[0].debug_info["search"]["target_index"] == "emb_code"

    # Test 2: Doc Query
    # "how to do this" should be classified as docs.
    results = search_spans("how to do this", repo_root=repo_root, debug=True)

    assert len(results) == 1
    assert results[0].span_hash == "hash_doc"
    assert results[0].debug_info["search"]["target_index"] == "embeddings"

    # Test 3: Disable Routing
    (repo_root / "llmc.toml").write_text("""
[embeddings.profiles.default_docs]
provider = "ignored"
model = "hash-emb-v1"
dim = 64

[embeddings.routes.docs]
profile = "default_docs"
index = "embeddings"

[routing.options]
enable_query_routing = false
""")

    # Clear config cache

    # Config caching removed, no need to clear
    # config.load_config.cache_clear()

    # Code query should now go to default docs index (embeddings)
    results = search_spans("def foo():", repo_root=repo_root, debug=True)

    assert len(results) == 1
    assert results[0].span_hash == "hash_doc"
    # target_index isn't set in debug info if routing is disabled/skipped in my implementation logic?
    # Let's check my implementation: "if route_decision: ... search_info['target_index'] = target_index"
    # If routing disabled, route_decision is None.
    # But we verify behavior by the fact we got hash_doc (from 'embeddings' table) instead of hash_code (from 'emb_code').
