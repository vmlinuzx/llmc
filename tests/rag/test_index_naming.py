import pytest
from llmc.rag.index_naming import resolve_index_name

def test_shared_mode_returns_base():
    """sharing="shared" returns just base"""
    assert resolve_index_name("emb_tech_docs", "llmc", "shared") == "emb_tech_docs"

def test_per_repo_mode_appends_repo():
    """sharing="per-repo" returns {base}_{repo}"""
    assert resolve_index_name("emb_tech_docs", "llmc", "per-repo") == "emb_tech_docs_llmc"

def test_suffix_appends():
    """suffix is appended when provided"""
    assert resolve_index_name("emb_tech_docs", "llmc", "per-repo", "_v1") == "emb_tech_docs_llmc_v1"

def test_empty_inputs():
    """handles empty strings gracefully"""
    assert resolve_index_name("", "", "per-repo") == "_"
