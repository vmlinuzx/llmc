import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmc.rlm.session import RLMResult
from llmc_mcp.config import McpRlmConfig
from llmc_mcp.tools.rlm import mcp_rlm_query


@pytest.fixture
def mock_session():
    with patch("llmc_mcp.tools.rlm.RLMSession") as mock:
        session_instance = mock.return_value
        session_instance.run = AsyncMock()
        yield session_instance

@pytest.fixture
def mock_validate_path():
    with patch("llmc_mcp.tools.rlm.validate_path") as mock:
        yield mock

@pytest.mark.asyncio
async def test_rlm_query_disabled():
    config = McpRlmConfig(enabled=False)
    result = await mcp_rlm_query({}, config, [], Path("/repo"))
    assert "error" in result
    assert result["meta"]["error_code"] == "tool_disabled"

@pytest.mark.asyncio
async def test_rlm_query_invalid_args():
    config = McpRlmConfig(enabled=True)
    
    # Missing task
    result = await mcp_rlm_query({"task": ""}, config, [], Path("/repo"))
    assert "error" in result
    assert result["meta"]["error_code"] == "invalid_args"
    
    # Both path and context
    result = await mcp_rlm_query({"task": "t", "path": "p", "context": "c"}, config, [], Path("/repo"))
    assert "error" in result
    assert result["meta"]["error_code"] == "invalid_args"
    
    # Neither path nor context
    result = await mcp_rlm_query({"task": "t"}, config, [], Path("/repo"))
    assert "error" in result
    assert result["meta"]["error_code"] == "invalid_args"

@pytest.mark.asyncio
async def test_rlm_query_context_success(mock_session):
    config = McpRlmConfig(enabled=True)
    mock_session.run.return_value = RLMResult(
        success=True, answer="42", session_id="test", budget_summary={}
    )
    
    result = await mcp_rlm_query(
        {"task": "meaning?", "context": "life"}, 
        config, [], Path("/repo")
    )
    
    assert "data" in result
    assert result["data"]["answer"] == "42"
    assert result["meta"]["source"]["type"] == "context"
    mock_session.load_context.assert_called_with("life")

@pytest.mark.asyncio
async def test_rlm_query_path_denied(mock_validate_path):
    config = McpRlmConfig(enabled=True)
    mock_validate_path.side_effect = PermissionError("Denied")
    
    result = await mcp_rlm_query(
        {"task": "analyze", "path": "/secret.env"}, 
        config, ["/repo"], Path("/repo")
    )
    
    assert "error" in result
    assert result["meta"]["error_code"] == "path_denied"

@pytest.mark.asyncio
async def test_rlm_query_file_too_large(mock_validate_path):
    config = McpRlmConfig(enabled=True, default_max_bytes=10)
    
    # Mock path resolution and file ops
    resolved_path = MagicMock()
    resolved_path.stat.return_value.st_size = 100
    mock_validate_path.return_value = resolved_path
    
    result = await mcp_rlm_query(
        {"task": "analyze", "path": "big.file"}, 
        config, ["/repo"], Path("/repo")
    )
    
    assert "error" in result
    assert result["meta"]["error_code"] == "file_too_large"

@pytest.mark.asyncio
@pytest.mark.parametrize("exception, error_check", [
    (httpx.ConnectError("Connection failed", request=MagicMock()), lambda r: "Connection failed" in str(r) or "error" in r),
    (httpx.TimeoutException("Timeout", request=MagicMock()), lambda r: "Timeout" in str(r) or "error" in r),
    (httpx.HTTPStatusError("500 Server Error", request=MagicMock(), response=MagicMock(status_code=500)), lambda r: "500" in str(r) or "error" in r),
    (json.JSONDecodeError("Invalid JSON", "doc", 0), lambda r: "JSON" in str(r) or "error" in r),
])
async def test_rlm_tool_backend_failures(mock_session, exception, error_check):
    config = McpRlmConfig(enabled=True)
    
    # Simulate backend failure by making session.run raise an exception
    mock_session.run.side_effect = exception
    
    result = await mcp_rlm_query(
        {"task": "analyze", "context": "test"}, 
        config, [], Path("/repo")
    )
    
    # Assert that the tool catches the exception and returns an error dictionary
    assert "error" in result
    # Optionally verify the error message contains relevant info
    # (Checking exact message might be brittle if implementation is generic)
