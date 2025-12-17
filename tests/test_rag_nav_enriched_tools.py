from unittest.mock import MagicMock, patch

import pytest

# We'll import these inside tests or after creating them to avoid import errors during initial run
# from llmc.rag_nav.models import SearchItem, EnrichmentData


class TestEnrichedTools:
    def test_model_enrichment_field(self):
        """Test that SearchItem accepts and serializes enrichment data."""
        try:
            from llmc.rag_nav.models import EnrichmentData, SearchItem, Snippet, SnippetLocation
        except ImportError:
            pytest.fail("Models not updated yet")

        enrich = EnrichmentData(summary="This is a summary", usage_guide="Use it well")
        item = SearchItem(
            file="test.py",
            snippet=Snippet(
                text="code", location=SnippetLocation(path="test.py", start_line=1, end_line=2)
            ),
            enrichment=enrich,
        )

        data = item.to_dict()
        assert "enrichment" in data
        assert data["enrichment"]["summary"] == "This is a summary"
        assert data["enrichment"]["usage_guide"] == "Use it well"

    def test_tool_search_attaches_graph_enrichment(self, tmp_path):
        """Test that tool_rag_search attaches enrichment from graph nodes."""
        try:
            from llmc.rag_nav.models import SearchItem, SearchResult, Snippet, SnippetLocation
            from llmc.rag_nav.tool_handlers import tool_rag_search
        except ImportError:
            pytest.fail("Modules not found")

        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Mock dependencies
        # 1. Mock _compute_route to use RAG
        # 2. Mock fts_search to return a hit
        # 3. Mock _load_graph to return enriched nodes

        mock_route = MagicMock()
        mock_route.use_rag = True
        mock_route.freshness_state = "FRESH"

        mock_hit = MagicMock()
        mock_hit.file = "src/auth.py"
        mock_hit.start_line = 10
        mock_hit.end_line = 20
        mock_hit.text = "def login(): pass"
        mock_hit.score = 1.0

        # Graph nodes with metadata
        mock_nodes = [
            {
                "id": "auth.login",
                "path": "src/auth.py",
                "start_line": 10,
                "end_line": 20,
                "metadata": {
                    "summary": "Authenticates user",
                    "usage_guide": "Call with credentials",
                },
            }
        ]

        with (
            patch("llmc.rag_nav.tool_handlers._compute_route", return_value=mock_route),
            patch("llmc.rag_nav.tool_handlers.fts_search", return_value=[mock_hit]),
            patch("llmc.rag_nav.tool_handlers._load_graph", return_value=(mock_nodes, [])),
            patch("llmc.rag_nav.tool_handlers.load_rerank_weights", return_value={}),
            patch("llmc.rag_nav.tool_handlers.rerank_hits", side_effect=lambda q, h, **k: h),
        ):  # Pass-through
            result = tool_rag_search(repo_root, "login")

            assert len(result.items) == 1
            item = result.items[0]
            assert item.enrichment is not None
            assert item.enrichment.summary == "Authenticates user"

    def test_tool_where_used_attaches_enrichment(self, tmp_path):
        """Test that where-used attaches enrichment."""
        from llmc.rag_nav.tool_handlers import tool_rag_where_used

        repo_root = tmp_path / "repo"

        mock_route = MagicMock()
        mock_route.use_rag = True
        mock_route.freshness_state = "FRESH"

        # Graph: Caller -> Callee
        # We want to see enrichment on the 'Caller' (the usage)
        mock_nodes = [
            {
                "id": "main",
                "path": "src/main.py",
                "start_line": 1,
                "end_line": 10,
                "metadata": {"summary": "Main entrypoint"},
            },
            {"id": "login", "path": "src/auth.py"},
        ]
        # Edge: main calls login
        # But wait, 'where_used("login")' -> returns 'main' (upstream)
        # The current tool implementation uses 'where_used_files_from_index' which returns paths.
        # Then it builds items.
        # The Phase 3 plan says we should use the GRAPH traversal if possible, or map paths back to nodes.

        # Ideally tool_rag_where_used should look up the node for the result path.

        with (
            patch("llmc.rag_nav.tool_handlers._compute_route", return_value=mock_route),
            patch("llmc.rag_nav.tool_handlers.load_graph_indices"),
            patch(
                "llmc.rag_nav.tool_handlers.where_used_files_from_index",
                return_value=["src/main.py"],
            ),
            patch("llmc.rag_nav.tool_handlers._load_graph", return_value=(mock_nodes, [])),
        ):
            result = tool_rag_where_used(repo_root, "login")

            assert len(result.items) == 1
            item = result.items[0]
            # We expect the tool to have matched src/main.py to the node "main" (by path)
            # and attached the summary.
            assert item.enrichment is not None
            assert item.enrichment.summary == "Main entrypoint"
