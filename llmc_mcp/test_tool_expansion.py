import asyncio
import json
import sys
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from llmc_mcp.server import LlmcMcpServer
from llmc_mcp.config import load_config

@pytest.mark.asyncio
async def test_rag_where_used_handler():
    config = load_config()
    server = LlmcMcpServer(config)
    
    mock_result = Mock()
    mock_result.to_dict.return_value = {"items": [], "symbol": "test_sym"}
    
    with patch("tools.rag_nav.tool_handlers.tool_rag_where_used", return_value=mock_result) as mock_tool:
        result = await server._handle_rag_where_used({"symbol": "test_sym"})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["symbol"] == "test_sym"
        mock_tool.assert_called_once()

@pytest.mark.asyncio
async def test_rag_lineage_handler():
    config = load_config()
    server = LlmcMcpServer(config)
    
    mock_result = Mock()
    mock_result.to_dict.return_value = {"items": [], "symbol": "test_sym", "direction": "downstream"}
    
    with patch("tools.rag_nav.tool_handlers.tool_rag_lineage", return_value=mock_result) as mock_tool:
        result = await server._handle_rag_lineage({"symbol": "test_sym"})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["direction"] == "downstream"
        mock_tool.assert_called_once()

@pytest.mark.asyncio
async def test_inspect_handler():
    config = load_config()
    server = LlmcMcpServer(config)
    
    mock_result = Mock()
    mock_result.to_dict.return_value = {"path": "test.py", "snippet": "code"}
    
    with patch("tools.rag.inspector.inspect_entity", return_value=mock_result) as mock_tool:
        result = await server._handle_inspect({"path": "test.py"})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["path"] == "test.py"
        mock_tool.assert_called_once()

@pytest.mark.asyncio
async def test_rag_stats_handler():
    config = load_config()
    server = LlmcMcpServer(config)
    
    mock_result = {"total_nodes": 100}
    
    with patch("tools.rag_nav.tool_handlers.tool_rag_stats", return_value=mock_result) as mock_tool:
        result = await server._handle_rag_stats({})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["total_nodes"] == 100
        mock_tool.assert_called_once()

@pytest.mark.asyncio
async def test_tools_registered():
    config = load_config()
    config.code_execution.enabled = False  # Force classic mode to see all tools
    server = LlmcMcpServer(config)
    tools = server.tools
    tool_names = {t.name for t in tools}
    
    assert "rag_where_used" in tool_names
    assert "rag_lineage" in tool_names
    assert "inspect" in tool_names
    assert "rag_stats" in tool_names
