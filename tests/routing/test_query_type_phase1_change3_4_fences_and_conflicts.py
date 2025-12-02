from llmc.routing.query_type import classify_query


def test_fence_positive_language_tag():
    q = '```python\nprint("hi")\n```'
    r = classify_query(q)
    assert r["route_name"] == "code"


def test_fence_positive_no_language():
    q = "```\nSELECT * FROM orders;\n```"
    r = classify_query(q)
    assert r["route_name"] == "code"


def test_fence_negative_single_backticks_inline():
    q = "This `backtick` is inline and not a fence; sku W-44910"
    r = classify_query(q)
    # Should not be forced to code merely by inline backticks; ERP may win or docs fallback
    assert r["route_name"] in {"erp", "docs", "code"}  # just ensure not forced by fence
    assert not any("fenced-code" in s for s in r.get("reasons", []))


def test_multiple_fenced_blocks_counts_as_code():
    q = "```python\na=1\n```\nBody text\n```\nSELECT 1;\n```"
    r = classify_query(q)
    assert r["route_name"] == "code"


def test_code_erp_conflict_fence_wins():
    q = "```python\ndef get_invoice(id):\n    return id\n```\nPlease check SKU W-44910"
    r = classify_query(q)
    assert r["route_name"] == "code"
    # ensures ERP cannot override fenced code
    reasons = " ".join(r.get("reasons", []))
    assert "fenced-code" in reasons or "priority:fenced-code" in reasons
