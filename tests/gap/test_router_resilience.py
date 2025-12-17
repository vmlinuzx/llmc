from unittest.mock import patch

from llmc.routing.query_type import classify_query


def test_router_resilience_heuristic_failure():
    """
    Test that classify_query catches exceptions from heuristic modules
    and falls back to a default route.
    """
    with patch(
        "llmc.routing.code_heuristics.score_all",
        side_effect=ValueError("Simulated failure"),
    ):
        # This should not raise an exception
        result = classify_query("how to install")

        # Verify fallback behavior (expecting 'docs' as default based on SDD)
        assert result["route_name"] == "docs"
