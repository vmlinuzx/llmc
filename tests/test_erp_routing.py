import pytest
from pathlib import Path
from llmc.routing.content_type import classify_slice
from llmc.routing.query_type import classify_query
from tools.rag.config import get_route_for_slice_type, load_config

def test_classify_slice_erp_path():
    # Simulate a path in an ERP import directory
    p = Path("data/imports/erp/products.json")
    res = classify_slice(p, "application/json", '{"id": 1}')
    assert res.slice_type == "erp_product"
    assert "erp path" in res.reasons[0]

def test_classify_slice_erp_content():
    # Simulate a random JSON file with ERP keys
    p = Path("temp/some_file.json")
    content = '{"sku": "W-1234", "price": 10.0}'
    res = classify_slice(p, "application/json", content)
    assert res.slice_type == "erp_product"
    assert "erp keys" in res.reasons[0]

def test_classify_query_sku():
    q = "Why is SKU W-44910 failing?"
    res = classify_query(q)
    assert res["route_name"] == "erp"
    assert "erp:sku" in res["reasons"][0]

def test_classify_query_keywords():
    q = "Check inventory of model number X100"
    res = classify_query(q)
    assert res["route_name"] == "erp"
    assert "erp:" in res["reasons"][0] or "conflict-policy" in res["reasons"][0]

def test_classify_query_tool_context():
    res = classify_query("some query", tool_context={"tool_id": "product_lookup"})
    assert res["route_name"] == "erp"
    assert res["confidence"] == 1.0

def test_config_mapping():
    # Verify that the config correctly maps erp_product -> erp
    # pytest changes CWD to a temp dir, so we must find the real repo root
    # This test file is at <repo>/tests/test_erp_routing.py
    repo_root = Path(__file__).resolve().parent.parent
    
    # Sanity check
    if not (repo_root / "llmc.toml").exists():
        pytest.skip("Cannot find llmc.toml at resolved repo root")

    route = get_route_for_slice_type("erp_product", repo_root=repo_root)
    assert route == "erp"
