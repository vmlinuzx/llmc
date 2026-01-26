import pytest

from llmc_mcp.config import McpConfig
from llmc_mcp.server import LlmcMcpServer


@pytest.mark.asyncio
async def test_rlm_tool_registered():
    config = McpConfig()
    config.rlm.enabled = True
    server = LlmcMcpServer(config)
    
    # LlmcMcpServer.tools is a list of Tool objects
    tool_names = [t.name for t in server.tools]
    assert "rlm_query" in tool_names
    
    # Check handler
    assert "rlm_query" in server.tool_handlers
    
    # Verify disabled if config disabled
    config_disabled = McpConfig()
    config_disabled.rlm.enabled = False
    server_disabled = LlmcMcpServer(config_disabled)
    
    # Tool definition is static in TOOLS list, so it might be present in tools list?
    # Let's check logic in _init_classic_mode
    # In classic mode, self.tools = list(TOOLS)
    # But handler is conditional.
    
    assert "rlm_query" in [t.name for t in server_disabled.tools]
    assert "rlm_query" not in server_disabled.tool_handlers
