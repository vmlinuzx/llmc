import pytest
from llmc_mcp.server import LlmcMcpServer
from llmc_mcp.config import McpConfig

@pytest.mark.asyncio
async def test_rlm_tool_registered():
    config = McpConfig()
    config.rlm.enabled = True
    server = LlmcMcpServer(config)
    
    # LlmcMcpServer.tools is a list of Tool objects
    tool_names = [t.name for t in server.tools]
    assert "run_rlm" in tool_names
    
    # Check handler
    assert "run_rlm" in server.tool_handlers
