import asyncio
from unittest.mock import AsyncMock

import pytest

from llmc_agent.agent import Agent
from llmc_agent.backends.base import GenerateResponse
from llmc_agent.config import AgentConfig, Config, OllamaConfig, RAGConfig
from llmc_agent.tools import Tool, ToolTier


# Dangerous Tool Implementation
class ExplosiveTool:
    def __init__(self):
        self.detonated = False

    def explode(self, intensity: int = 1):
        self.detonated = True
        return f"BOOM! Intensity {intensity}"


async def _test_logic():
    """
    Async logic for the test.
    """

    # 1. Setup Mock Config
    config = Config(
        ollama=OllamaConfig(url="http://mock:11434"),
        rag=RAGConfig(enabled=False),
        agent=AgentConfig(model="mock-model"),
    )

    agent = Agent(config)

    # 2. Register dangerous tool
    explosive_tool_impl = ExplosiveTool()

    dangerous_tool = Tool(
        name="explode",
        description="Destroys everything",
        tier=ToolTier.RUN,
        function=explosive_tool_impl.explode,
        parameters={"type": "object", "properties": {"intensity": {"type": "integer"}}},
        requires_confirmation=True,  # CRITICAL FLAG
    )

    # Inject tool into agent's registry
    agent.tools._register(dangerous_tool)

    # 3. Mock Ollama Backend
    mock_ollama = AsyncMock()

    tool_call_payload = {
        "function": {
            "name": "explode",
            "arguments": '{"intensity": 9000}',  # Ollama usually returns JSON string for arguments
        },
        "id": "call_123",
    }

    # First response: Call the tool
    response_with_tool = GenerateResponse(
        content="",
        model="mock-model",
        tokens_prompt=10,
        tokens_completion=10,
        finish_reason="tool_calls",
        tool_calls=[tool_call_payload],
    )

    # Second response: After tool execution
    response_final = GenerateResponse(
        content="I have destroyed it.",
        model="mock-model",
        tokens_prompt=20,
        tokens_completion=5,
        finish_reason="stop",
    )

    mock_ollama.generate_with_tools.side_effect = [response_with_tool, response_final]

    agent.ollama = mock_ollama

    # 4. Execute
    # "please delete" triggers RUN tier via detect_intent_tier (destroy is not in keywords)
    await agent.ask_with_tools("please delete everything")

    # 5. Assert
    # We assert that the tool was NOT detonated.
    # Since the vulnerability exists, self.detonated will be True, and this assertion will fail.
    assert (
        not explosive_tool_impl.detonated
    ), "SECURITY FAILURE: Tool with requires_confirmation=True was executed automatically!"


@pytest.mark.allow_network
def test_security_confirmation_bypass():
    """

    SDD: tests/gap/SDDs/SDD-Safety-ConfirmationBypass.md



    Test that a tool marked with requires_confirmation=True

    is NOT executed automatically by the agent.



    This test is EXPECTED TO FAIL currently, demonstrating the vulnerability.

    """

    asyncio.run(_test_logic())
