
from llmc.routing.query_type import classify_query

def _is_code(result):
    return result.get("route_name") == "code"

def test_simple_assignment_is_code():
    r = classify_query("x = 5")
    assert _is_code(r)

def test_simple_function_call_is_code():
    r = classify_query("print('hello')")
    assert _is_code(r)

def test_imports_are_code():
    r = classify_query("import os\nfrom sys import argv")
    assert _is_code(r)

def test_loop_is_code():
    r = classify_query("for i in range(3):\n    print(i)")
    assert _is_code(r)

def test_lambda_is_code():
    r = classify_query("f = lambda x: x*2")
    assert _is_code(r)

def test_code_with_erp_words_routes_code():
    q = "def get_invoice(id):\n    return id"
    r = classify_query(q)
    assert _is_code(r)

def test_pure_erp_intent_routes_erp_or_docs():
    q = "how do I look up an invoice in ERP"
    r = classify_query(q)
    assert r["route_name"] in {"erp","docs"}
