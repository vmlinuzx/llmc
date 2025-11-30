
from llmc.routing.query_type import classify_query

def test_priority_fenced_code_beats_erp():
    q = '```python\ndef get_invoice(i):\n    return i\n```'
    r = classify_query(q)
    assert r["route_name"] == "code"
    assert any("fenced-code" in s for s in r.get("reasons", []))

def test_priority_code_structure_beats_erp_keywords():
    q = "def handler(sku):\n    return sku"
    r = classify_query(q)
    assert r["route_name"] == "code"
    assert any("code-structure" in s for s in r.get("reasons", []))

def test_priority_code_keywords_before_erp_keywords():
    # Needs 2 keywords to trigger code detection in Phase 1
    q = "return from sku"
    r = classify_query(q)
    assert r["route_name"] == "code"
    assert any("code-keywords" in s for s in r.get("reasons", []))
