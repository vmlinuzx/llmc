from pathlib import Path
import unittest
from unittest.mock import patch

from llmc.client import RAGClient
from llmc.rag_nav.tool_handlers import tool_rag_lineage  # noqa: F401


class TestRAGClient(unittest.TestCase):
    @patch('llmc.client.tool_rag_lineage')
    def test_lineage_with_invalid_direction_defaults_to_downstream(self, mock_tool_lineage):
        # Setup
        repo_root = Path('/fake/repo')
        client = RAGClient(repo_root)
        
        # Action
        client.lineage(symbol='foo', direction='sideways')
        
        # Assert
        mock_tool_lineage.assert_called_once()
        
        # Verify arguments passed to the mock
        # signature: tool_rag_lineage(repo_root, symbol, direction, limit)
        args, _ = mock_tool_lineage.call_args
        self.assertEqual(args[0], repo_root)
        self.assertEqual(args[1], 'foo')
        self.assertEqual(args[2], 'sideways')

    @patch('llmc.client.tool_rag_search')
    def test_search_calls_underlying_tool(self, mock_tool_search):
        # Setup
        repo_root = Path('/fake/repo')
        client = RAGClient(repo_root)
        query = "test query"
        limit = 10
        
        # Action
        client.search(query, limit=limit)
        
        # Assert
        mock_tool_search.assert_called_once_with(repo_root, query, limit)

    @patch('llmc.client.tool_rag_search')
    def test_search_handles_no_limit(self, mock_tool_search):
        # Setup
        repo_root = Path('/fake/repo')
        client = RAGClient(repo_root)
        query = "test query"
        
        # Action
        client.search(query)
        
        # Assert
        mock_tool_search.assert_called_once_with(repo_root, query, None)
