import pytest
from llmc_mcp.tools.rlm import RLMTool
from llmc_mcp.config import RLMConfig

def test_rlm_tool_initialization():
    config = RLMConfig(enabled=True)
    tool = RLMTool(config)
    assert tool.name == "run_rlm"
    assert "recursive" in tool.description.lower()

@pytest.mark.asyncio
async def test_rlm_tool_execution_disabled():
    config = RLMConfig(enabled=False)
    tool = RLMTool(config)
    with pytest.raises(ValueError, match="RLM is disabled"):
        await tool.run({"goal": "test"})
