from llmc.routing.query_type import classify_query


def test_conflict_prefers_code_by_default(monkeypatch):
    q = "```python\ndef get_invoice(id):\n    return id\n```\nSKU W-44910"
    r = classify_query(q)
    assert r["route_name"] == "code"
    assert any("prefer-code" in s or "fenced-code" in s for s in r.get("reasons", []))


def test_conflict_toggle_prefers_erp(monkeypatch):
    monkeypatch.setenv("LLMC_ROUTING_PREFER_CODE_ON_CONFLICT", "false")
    q = "return sku W-44910"
    r = classify_query(q)
    assert r["route_name"] == "erp"
    monkeypatch.delenv("LLMC_ROUTING_PREFER_CODE_ON_CONFLICT", raising=False)
