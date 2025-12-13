from pathlib import Path


def run_extractor_smoke(sample_dir: str) -> tuple[bool, dict]:
    """Run extractor on sample files, verify chunks produced.

    Returns:
        (passed, results) where results contains per-file chunk counts
    """
    # Import inside function to allow for optional dependencies or mocking in tests
    # if the environment isn't fully set up, though typically we expect it to be.
    from tools.rag.extractors.tech_docs import TechDocsExtractor

    extractor = TechDocsExtractor()
    results = {}
    path = Path(sample_dir)

    if not path.exists():
        return False, {"error": f"Sample directory {sample_dir} not found"}

    md_files = list(path.glob("*.md"))
    if not md_files:
        # If we expect files but find none, that's a failure of the test setup
        # or the input provided.
        return False, {"error": "No .md files found in sample directory"}

    for file_path in md_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            chunks = list(extractor.extract(file_path, content))
            results[str(file_path)] = len(chunks)
        except Exception:
            # If extraction fails, we record -1 or 0.
            # 0 chunks is a failure condition anyway.
            results[str(file_path)] = 0

    # Fail if any file produces 0 chunks
    passed = len(results) > 0 and all(count > 0 for count in results.values())
    return passed, results
