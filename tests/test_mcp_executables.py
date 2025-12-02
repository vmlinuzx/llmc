

import pytest

from llmc_mcp.config import McpConfig
from llmc_mcp.server import LlmcMcpServer


@pytest.mark.asyncio
async def test_dynamic_executables():
    # Setup config with a custom executable
    config = McpConfig()
    # We use 'echo' as the executable for simplicity
    config.tools.executables = {
        "echo_test": "echo"
    }
    
    # Initialize server
    server = LlmcMcpServer(config)
    
    # Verify tool registration
    tools = server.tools
    tool_names = [t.name for t in tools]
    assert "echo_test" in tool_names
    
    # Verify handler exists
    assert "echo_test" in server.tool_handlers
    
    # Call the tool
    handler = server.tool_handlers["echo_test"]
    result = await handler({"args": ["hello", "world"]})
    
    # Verify result
    assert len(result) == 1
    import json
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["stdout"].strip() == "hello world"
