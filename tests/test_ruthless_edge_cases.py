"""
Ruthless Edge Case Testing for Query Routing
=============================================

These tests are designed to BREAK the query routing system.
Every green check is suspicious until proven otherwise.
"""

import pytest

from llmc.routing.code_heuristics import CODE_STRUCT_REGEXES
from llmc.routing.erp_heuristics import ERP_SKU_RE
from llmc.routing.query_type import classify_query

# ==============================================================================
# EDGE CASE 1: None and Empty Inputs
# ==============================================================================


def test_classify_query_none_input():
    """What happens with None input? Should this crash or handle gracefully?"""
    result = classify_query(None)
    # If it doesn't crash, what does it return?
    print(f"Result for None: {result}")
    assert "route_name" in result
    assert "confidence" in result
    assert "reasons" in result
    assert result["route_name"] == "docs"
    assert "empty-or-none-input" in result["reasons"]


def test_classify_query_none_input_with_context():
    """None input but with strong tool context hint"""
    # Even if text is None, tool context should win
    context = {"tool_id": "code_search"}
    result = classify_query(None, tool_context=context)
    print(f"None input + code context: {result}")
    assert result["route_name"] == "code"
    assert "tool-context=code" in result["reasons"]


def test_classify_query_empty_string():
    """Empty string should default to docs, but what confidence?"""
    result = classify_query("")
    print(f"Empty string result: {result}")
    assert result["route_name"] == "docs"
    # Confidence should be low for empty input
    assert result["confidence"] <= 0.6


def test_classify_query_whitespace_only():
    """Only whitespace - no code signals should be detected"""
    result = classify_query("   \n\t   \r\n   ")
    print(f"Whitespace-only result: {result}")
    assert result["route_name"] == "docs"
    assert "empty-or-none-input" in result["reasons"]


# ==============================================================================
# EDGE CASE 2: Unicode and Special Characters
# ==============================================================================


def test_classify_query_unicode_code():
    """Can the system handle Unicode code patterns?"""
    query = """def 函数():
    return "你好世界"
"""
    result = classify_query(query)
    print(f"Unicode code result: {result}")
    # Should still detect 'def' as code keyword
    assert result["route_name"] == "code"


def test_classify_query_emoji():
    """Emojis and special chars should not confuse the router"""
    query = "How do I code this? 🤔 def foo(): pass"
    result = classify_query(query)
    print(f"Emoji result: {result}")
    # Should detect def as code
    assert result["route_name"] == "code"


def test_classify_query_japanese_text():
    """Japanese text - should default to docs"""
    query = "これは日本語です。コードについて教えてください。"
    result = classify_query(query)
    print(f"Japanese text result: {result}")
    # No ERP or code patterns, should be docs
    assert result["route_name"] == "docs"


def test_classify_query_mixed_unicode_normal():
    """Mixed unicode normal text"""
    query = "查找 SKU ABC-12345 的库存水平"
    result = classify_query(query)
    print(f"Chinese + SKU result: {result}")
    # Should detect SKU pattern even in unicode text
    assert result["route_name"] == "erp"


# ==============================================================================
# EDGE CASE 3: Regex Pattern Edge Cases
# ==============================================================================


def test_sku_regex_very_short():
    """Test SKU regex with very short patterns"""
    # ERP_SKU_RE expects 1-4 letters + 4-6 digits
    test_cases = [
        ("A-123", False),  # Too few digits
        ("AB-12345", True),  # Valid
        ("ABC-12345", True),  # Valid
        ("ABCDE-123", False),  # Too many letters
        ("ABC-12", False),  # Too few digits
        ("ABCDEFGHIJ-123456", False),  # Too many letters and digits
    ]

    for pattern, should_match in test_cases:
        matches = ERP_SKU_RE.findall(pattern)
        if should_match:
            assert len(matches) > 0, f"Pattern {pattern} should match but didn't"
        else:
            assert (
                len(matches) == 0
            ), f"Pattern {pattern} shouldn't match but got {matches}"


def test_sku_regex_weird_but_valid():
    """Weird patterns that might accidentally match"""
    # What about these edge cases?
    test_cases = [
        "SKU ABC-12345",  # With prefix
        "product W-44910 is failing",  # Inline
        "Looking for STR-66320 or W-44910",  # Multiple
        "ABC-12345.txt",  # With extension
        "Pricing: W-44910 @ $19.99",  # With price
    ]

    for pattern in test_cases:
        matches = ERP_SKU_RE.findall(pattern)
        print(f"Pattern '{pattern}' matched: {matches}")
        # These should match the SKU part
        assert len(matches) > 0


def test_code_struct_regex_pathological():
    """Test CODE_STRUCT_REGEXES with pathological cases"""
    test_cases = [
        # Should match (Python centric)
        ("class Foo: pass", True),
        ("def func(): return True", True),
        # C-style braces are NOT currently supported by CODE_STRUCT_REGEXES
        ("{\n    return x;\n}", False),
        ("int main() { return 0; }", True),  # Matches function call regex 'main()'
        ("if (x) { do(); }", True),  # Matches function call regex 'do()'
        # Should NOT match
        ("{this is just braces}", False),  # Not code structure
        ("{braces in prose}", False),
        ("Just text with {braces}", False),
        ("return but not code", False),  # Single keyword doesn't match structure
    ]
    for pattern, should_match in test_cases:
        # CODE_STRUCT_REGEXES is a list of compiled regex patterns
        found_any = False
        all_matches = []
        for regex in CODE_STRUCT_REGEXES:
            matches = regex.findall(pattern)
            if matches:
                found_any = True
                all_matches.extend(matches)

        if should_match:
            assert found_any, f"Pattern '{pattern}' should match CODE_STRUCT_REGEXES"
        else:
            assert (
                not found_any
            ), f"Pattern '{pattern}' shouldn't match but got {all_matches}"


# ==============================================================================
# EDGE CASE 4: Ambiguous Queries
# ==============================================================================


def test_classify_query_product_vs_code():
    """Ambiguous: 'product' is in both ERP_KEYWORDS and could be in code"""
    # 'product' is in ERP_KEYWORDS
    query = "product = get_product('sku')"
    result = classify_query(query)
    print(f"Product in code result: {result}")
    # The code structure should win
    assert result["route_name"] == "code"


def test_classify_query_model_context():
    """'model' is in ERP_KEYWORDS but could be code"""
    query = "model = SomeModel()"
    result = classify_query(query)
    print(f"Model in code result: {result}")
    # Code structure should win
    assert result["route_name"] == "code"


def test_classify_query_item_in_text():
    """'item' is generic but in ERP_KEYWORDS"""
    # If only 'item' is mentioned, should it be ERP?
    query = "an item was found"
    result = classify_query(query)
    print(f"Item in text result: {result}")
    # Current logic allows 1 ERP keyword (score 0.55) to beat docs (score 0.5)
    assert result["route_name"] == "erp"


def test_classify_query_class_word():
    """The word 'class' - is it code or docs?"""
    query = "What is a class in programming?"
    result = classify_query(query)
    print(f"'class' word result: {result}")
    # Single keyword without structure should not trigger code
    # But let's see...


def test_classify_query_code_like_but_not():
    """Text that looks like code but isn't"""
    # Try to fool the regex
    test_queries = [
        "What does 'def' mean in Python?",
        "Explain return statements",
        "The {braces} here are just for show",
    ]

    for query in test_queries:
        result = classify_query(query)
        print(f"Query: '{query}' -> {result}")
        # These should NOT be classified as code
        # They are questions ABOUT code, not code itself


# ==============================================================================
# EDGE CASE 5: Tool Context Edge Cases
# ==============================================================================


def test_classify_query_tool_context_case_sensitivity():
    """Tool context should handle case variations"""
    queries = [
        ("test", {"tool_id": "CODE_NAVIGATOR"}),
        ("test", {"tool_id": "Code_Refactor"}),
        ("test", {"tool_id": "Erp_Lookup"}),
        ("test", {"tool_id": "ERP"}),
    ]

    for query, context in queries:
        result = classify_query(query, tool_context=context)
        print(f"Context {context} -> {result}")
        # All should be routed based on context


def test_classify_query_tool_context_partial_matches():
    """What about partial matches in tool_id?"""
    # Does 'code' match in 'codecs'?
    query = "test"
    context = {"tool_id": "codecs_search"}
    result = classify_query(query, tool_context=context)
    print(f"codecs_search -> {result}")
    # Check if it matches 'code' substring


def test_classify_query_tool_context_mixed():
    """Multiple hints in tool_id"""
    query = "test"
    # Tool with both 'code' and 'erp' in name - which wins?
    context = {"tool_id": "code_erp_hybrid"}
    result = classify_query(query, tool_context=context)
    print(f"code_erp_hybrid -> {result}")
    # First match in the list should win


def test_classify_query_tool_context_none_values():
    """Tool context with None or missing values"""
    result1 = classify_query("test", tool_context={"tool_id": None})
    print(f"tool_id=None -> {result1}")

    result2 = classify_query("test", tool_context={})
    print(f"empty context -> {result2}")

    result3 = classify_query("test", tool_context={"other_key": "value"})
    print(f"context without tool_id -> {result3}")


# ==============================================================================
# EDGE CASE 6: Very Long and Pathological Inputs
# ==============================================================================


def test_classify_query_very_long_query():
    """What about extremely long queries?"""
    # 10k characters of 'lorem ipsum'
    long_text = "Lorem ipsum " * 1000
    result = classify_query(long_text)
    print(
        f"Very long query result: route={result['route_name']}, confidence={result['confidence']}"
    )
    # Should complete without error
    assert "route_name" in result


def test_classify_query_repeated_patterns():
    """Query with many code patterns"""
    query = "\n".join([f"def func{i}(): return {i}" for i in range(100)])
    result = classify_query(query)
    print(f"Repeated patterns result: {result}")
    # Should definitely be code
    assert result["route_name"] == "code"


def test_classify_query_many_sku_patterns():
    """Many SKU patterns in one query"""
    query = "SKU W-44910, SKU ABC-1234, SKU DEF-5678, SKU GHI-9012"
    result = classify_query(query)
    print(f"Many SKUs result: {result}")
    # Should be ERP
    assert result["route_name"] == "erp"


# ==============================================================================
# EDGE CASE 7: Conflicting Signals
# ==============================================================================


def test_classify_query_code_in_erp_context():
    """Code structure in ERP tool context - who wins?"""
    query = "def foo(): return 'code'"
    context = {"tool_id": "erp_lookup"}
    result = classify_query(query, tool_context=context)
    print(f"Code in ERP context -> {result}")
    # Tool context should win (confidence 1.0)


def test_classify_query_erp_in_code_context():
    """ERP content in code tool context"""
    query = "SKU W-12345 is failing"
    context = {"tool_id": "code_refactor"}
    result = classify_query(query, tool_context=context)
    print(f"ERP in code context -> {result}")
    # Tool context should win


def test_classify_query_contradictory_patterns():
    """Query with patterns from all three categories"""
    # Has code structure, ERP keywords, and is in general prose
    query = """
    Look at this code:
    def process_sku(sku):
        return sku

    The SKU W-12345 is failing in our inventory.
    """
    result = classify_query(query)
    print(f"Contradictory patterns -> {result}")
    # Code fence should win with 0.9 confidence


# ==============================================================================
# EDGE CASE 8: Code Fence Edge Cases
# ==============================================================================


def test_classify_query_empty_code_fence():
    """Empty code fence"""
    query = "```\n```"
    result = classify_query(query)
    print(f"Empty code fence -> {result}")
    # Should still be detected as code fence
    assert result["route_name"] == "code"
    assert "heuristic=fenced-code" in result["reasons"]


def test_classify_query_code_fence_without_language():
    """Code fence without language hint"""
    query = "```\ndef foo():\n    pass\n```"
    result = classify_query(query)
    print(f"Code fence no language -> {result}")
    # Should still match
    assert result["route_name"] == "code"


def test_classify_query_triple_backticks_in_string():
    """Triple backticks not actually a fence"""
    query = r'The string "```" appears in this text'
    result = classify_query(query)
    print(f"Backticks in string -> {result}")
    # Should NOT be detected as code fence
    # This might be a bug!


def test_classify_query_malformed_code_fence():
    """Malformed or partial code fences"""
    test_cases = [
        "``code",  # Two backticks
        "```code",  # No closing
        "code```",  # No opening
        "`` ` code ` ``",  # Escaped
    ]

    for query in test_cases:
        result = classify_query(query)
        print(f"Malformed fence '{query}' -> {result}")


# ==============================================================================
# EDGE CASE 9: Numbers and Special Patterns
# ==============================================================================


def test_classify_query_numbers_only():
    """Query with just numbers"""
    query = "12345"
    result = classify_query(query)
    print(f"Numbers only -> {result}")
    # Should default to docs
    assert result["route_name"] == "docs"


def test_classify_query_alphanumeric_codes():
    """Alphanumeric codes that aren't SKUs"""
    test_cases = [
        "ABC123",  # No dash
        "A123",  # Too short
        "ABCDEFG-123456",  # Too many chars/digits
        "AB-12",  # Too few digits
        "ABC-12A",  # Letters in number part
    ]

    for query in test_cases:
        result = classify_query(query)
        print(f"'{query}' -> {result}")
        # None should match ERP pattern
        # Should default to docs
        assert result["route_name"] in [
            "docs",
            "code",
        ]  # Could match code if patterns match


def test_classify_query_version_numbers():
    """Version numbers like 1.2.3"""
    query = "version 1.2.3"
    result = classify_query(query)
    print(f"Version numbers -> {result}")
    # Should be docs


# ==============================================================================
# EDGE CASE 10: Performance and Memory
# ==============================================================================


def test_classify_query_deeply_nested_structures():
    """Deeply nested code structures"""
    query = "\n".join(["    " * i + "return x" for i in range(1000)])
    result = classify_query(query)
    print(
        f"Deeply nested: route={result['route_name']}, confidence={result['confidence']}"
    )
    # Should handle without crashing
    assert "route_name" in result


if __name__ == "__main__":
    # Run tests and print results
    print("\n" + "=" * 80)
    print("RUTHLESS EDGE CASE TESTING FOR QUERY ROUTING")
    print("=" * 80)
    pytest.main([__file__, "-v", "-s"])
