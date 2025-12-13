def resolve_index_name(base: str, repo: str, sharing: str, suffix: str = "") -> str:
    """Resolve final index name based on sharing strategy.
    
    Args:
        base: Base index name (e.g., "emb_tech_docs")
        repo: Repository name (e.g., "llmc")
        sharing: "shared" or "per-repo"
        suffix: Optional deployment suffix
        
    Returns:
        Final index name (e.g., "emb_tech_docs_llmc")
    """
    return base if sharing == "shared" else f"{base}_{repo}{suffix}"
