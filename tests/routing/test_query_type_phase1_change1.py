

from llmc.routing.query_type import classify_query


def test_classify_query_none_returns_docs_low_confidence():
    result = classify_query(None)
    assert isinstance(result, dict)
    assert result.get("route_name") == "docs"
    assert result.get("confidence") <= 0.3
    assert any("empty-or-none-input" in r for r in result.get("reasons", []))

def test_classify_query_whitespace_returns_docs_low_confidence():
    result = classify_query("   \n\t")
    assert isinstance(result, dict)
    assert result.get("route_name") == "docs"
    assert result.get("confidence") <= 0.3
    assert any("empty-or-none-input" in r for r in result.get("reasons", []))
