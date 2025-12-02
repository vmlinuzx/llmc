

from llmc.routing.query_type import classify_query


def test_phase4_refactor_keeps_behavior_simple_code():
    r = classify_query("x = 5")
    assert r["route_name"] == "code"

def test_phase4_toml_policy_tie_prefers_erp(tmp_path, monkeypatch):
    toml = tmp_path / "llmc.toml"
    toml.write_text('''
[routing.erp_vs_code]
prefer_code_on_conflict = false
conflict_margin = 0.2
''', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = classify_query("return sku W-44910")
    assert r["route_name"] == "erp"

def test_phase4_metrics_reasons_present():
    r = classify_query("def hello():\n    return 1")
    assert isinstance(r.get("reasons"), list)
    assert r["route_name"] == "code"
