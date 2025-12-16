import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from llmc_agent.agent import Agent
from llmc_agent.config import AgentConfig
from llmc_agent.tools import ToolRegistry, Tool, ToolTier

from llmc_agent.backends.base import GenerateResponse, GenerateRequest # Import GenerateResponse

# Define a large string to simulate context overflow
VERY_LARGE_STRING = "A" * 50_000

class TestAgentContextOverflow:

    @pytest.fixture
    def agent_config(self):
        """Fixture for agent configuration with a small context budget."""
        # Create a mock config object with the necessary attributes
        mock_ollama_config = MagicMock()
        mock_ollama_config.url = "http://localhost:11434"
        mock_ollama_config.timeout = 300
        mock_ollama_config.temperature = 0.0
        mock_ollama_config.num_ctx = 4096 # Standard context window size

        mock_rag_config = MagicMock()
        mock_rag_config.enabled = False # Disable RAG for this test

        config = AgentConfig()
        config.ollama = mock_ollama_config
        config.rag = mock_rag_config
        config.context_budget = 4000  # Set a small context budget for the agent
        config.agent = MagicMock() # Mock agent section
        config.agent.model = "mock_model"
        config.agent.response_reserve = 1024 # Standard response reserve

        return config

    # Patch OllamaBackend and ToolRegistry at the class level
    @patch('llmc_agent.agent.OllamaBackend')
    @patch('llmc_agent.tools.ToolRegistry')
    @pytest.mark.asyncio # Mark the test as async
    async def test_unbounded_tool_output_context_overflow(
        self,
        MockToolRegistry, # This is the mocked class
        MockOllamaBackend, # This is the mocked class
        agent_config
    ):
        """
        Tests that a large tool output causes context overflow by not being truncated
        before being sent back to the LLM.
        """
        # Create instances of the mocked classes
        mock_ollama_backend_instance = MockOllamaBackend.return_value
        mock_tool_registry_instance = MockToolRegistry.return_value

        def _verbose_tool_func():
            return VERY_LARGE_STRING

        # Create a Tool instance
        mock_verbose_tool = Tool(
            name="verbose_tool",
            description="Returns a very large string.",
            tier=ToolTier.WALK, # Or any appropriate tier
            function=_verbose_tool_func,
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )

        # Configure the mocked tool registry instance
        mock_tool_registry_instance.get_tool.side_effect = lambda name: mock_verbose_tool if name == "verbose_tool" else None
        mock_tool_registry_instance.get_tools_for_tier.return_value = [mock_verbose_tool]
        mock_tool_registry_instance.unlock_tier = MagicMock() # Mock the unlock_tier method
        
        # Configure the mocked OllamaBackend instance's generate_with_tools method
        mock_ollama_backend_instance.generate_with_tools = AsyncMock(side_effect=[
            # First call to generate_with_tools: LLM requests to use verbose_tool
            GenerateResponse(
                content="",
                tokens_prompt=100,
                tokens_completion=50,
                model="mock_model",
                finish_reason="tool_calls",
                tool_calls=[{"function": {"name": "verbose_tool", "arguments": {}}}],
            ),
            # Second call to generate_with_tools: LLM processes tool output
            GenerateResponse(
                content="Some final response after processing the verbose tool output.",
                tokens_prompt=200,
                tokens_completion=100,
                model="mock_model",
                finish_reason="stop",
                tool_calls=[],
            )
        ])

        # Initialize the agent (it will use the patched classes)
        agent = Agent(config=agent_config)

        # 2. Call agent.ask_with_tools, which should trigger the tool call
        await agent.ask_with_tools("Please use the verbose tool to give me some information.")

        # 3. Assertions
        # The generate_with_tools method should have been called twice
        assert mock_ollama_backend_instance.generate_with_tools.call_count == 2

        # Get the messages from the second call to generate_with_tools
        # This is where the tool output would be passed back to the LLM
        second_call_args, _ = mock_ollama_backend_instance.generate_with_tools.call_args_list[1]
        messages_sent_to_llm = second_call_args[0].messages # Access messages attribute of GenerateRequest

        # Find the tool output message in the list
        tool_output_message = None
        for message in messages_sent_to_llm:
            if message.get("role") == "tool": # Check for tool role
                tool_output_message = message
                break

        assert tool_output_message is not None, "Tool output message not found in the second LLM call."
        
        # Assert that the content of the tool output message is the full, untruncated string
        assert tool_output_message["content"] == json.dumps(VERY_LARGE_STRING) # Tool output is json dumped
        assert len(json.loads(tool_output_message["content"])) == len(VERY_LARGE_STRING)
        assert len(json.loads(tool_output_message["content"])) == 50_000

        # Further assert that the content length is significantly larger than the context budget
        # This explicitly demonstrates the overflow
        # Note: The context budget here is for the agent, not directly for the LLM backend's message list length
        # The key assertion is that the original large string is passed without truncation.
        # The prompt assembly part of the agent is responsible for respecting the context budget,
        # but the SDD states the tool output is appended directly without checking size.
        # So we assert that the raw tool output length is still the large length.