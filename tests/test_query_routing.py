import pytest
from llmc.routing.query_type import classify_query

def test_classify_query_code_snippet():
    query = """
    def hello_world():
        print("Hello")
        return True
    """
    result = classify_query(query)
    assert result["route_name"] == "code"
    assert result["confidence"] >= 0.7
    assert "keywords=def" in str(result["reasons"]) or "pattern=def" in str(result["reasons"])

def test_classify_query_natural_language():
    query = "How do I configure the LLMC routing in the toml file?"
    result = classify_query(query)
    assert result["route_name"] == "docs"
    assert "default=docs" in result["reasons"]

def test_classify_query_tool_context_code():
    result = classify_query("some ambiguous text", tool_context={"tool_id": "code_refactor"})
    assert result["route_name"] == "code"
    assert result["confidence"] == 1.0
    assert "tool_context=code_refactor" in result["reasons"]

def test_classify_query_tool_context_erp():
    result = classify_query("sku 12345", tool_context={"tool_id": "erp_lookup"})
    assert result["route_name"] == "docs"
    assert result["confidence"] == 1.0

def test_classify_query_code_fences():
    query = "Here is the code: ```python\nprint('hi')\n```"
    result = classify_query(query)
    assert result["route_name"] == "code"
    assert "heuristic=code_fences" in result["reasons"]

def test_classify_query_c_style():
    query = "int main() { return 0; }"
    result = classify_query(query)
    assert result["route_name"] == "code"
