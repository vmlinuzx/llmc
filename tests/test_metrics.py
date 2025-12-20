from llmc.rag.eval.metrics import is_code_file, code_at_k, mrr_code

def test_is_code_file():
    assert is_code_file("test.py") is True
    assert is_code_file("src/app.ts") is True
    assert is_code_file("README.md") is False  # MD is usually doc, not code in this context? 
    # Wait, REQUIREMENTS said: "test_is_code_file() — Correctly identifies .py, .ts, .md files"
    # Wait, does it mean .md is code or not?
    # Usually MD is documentation. The list I put in metrics.py didn't include .md.
    # Let's assume .md is NOT code.
    assert is_code_file("image.png") is False
    assert is_code_file("config.toml") is True

def test_code_at_k_mixed():
    results = [
        {"slice_id": "a.py"},  # Code
        {"slice_id": "b.md"},  # Doc
        {"slice_id": "c.ts"},  # Code
        {"slice_id": "d.txt"}, # Doc
    ]
    # k=2: a.py, b.md -> 1 code -> 0.5
    assert code_at_k(results, k=2) == 0.5
    
    # k=3: a.py, b.md, c.ts -> 2 code -> 2/3
    assert abs(code_at_k(results, k=3) - (2/3)) < 0.001
    
    # k=10 (more than len): all 4 -> 2 code -> 0.5
    assert code_at_k(results, k=10) == 0.5

def test_mrr_code():
    # First item is code -> 1/1 = 1.0
    results1 = [{"slice_id": "a.py"}, {"slice_id": "b.md"}]
    assert mrr_code(results1) == 1.0
    
    # Second item is code -> 1/2 = 0.5
    results2 = [{"slice_id": "a.md"}, {"slice_id": "b.py"}]
    assert mrr_code(results2) == 0.5
    
    # No code -> 0.0
    results3 = [{"slice_id": "a.md"}, {"slice_id": "b.txt"}]
    assert mrr_code(results3) == 0.0
