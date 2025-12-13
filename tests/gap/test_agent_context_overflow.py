import unittest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

from llmc_agent.agent import Agent
from llmc_agent.config import Config

# Mock response class for OllamaBackend
@dataclass
class MockResponse:
    content: str
    tokens_prompt: int
    tokens_completion: int
    model: str
    tool_calls: list = None

class TestAgentContextOverflow(unittest.IsolatedAsyncioTestCase):

    async def test_context_overflow(self):
        # 1. Setup
        # Create config with small context budget
        config = Config()
        config.agent.context_budget = 100
        config.agent.response_reserve = 10
        config.agent.model = "test-model"
        config.ollama.url = "http://localhost:11434"
        config.ollama.timeout = 30
        config.ollama.temperature = 0.0
        config.ollama.num_ctx = 2048
        config.rag.enabled = False
        config.rag.include_summary = False

        # Mock count_tokens to return 1 token per char
        with patch("llmc_agent.agent.count_tokens", side_effect=len) as mock_count_tokens:
            
            agent = Agent(config)
            
            # Mock the backend
            agent.ollama = AsyncMock()
            
            # Define tool call
            tool_call = {
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "file.txt"}
                },
                "id": "call_123"
            }

            # Define side effects for generate_with_tools
            # Iteration 1: Return tool call
            # Iteration 2: Return final answer
            agent.ollama.generate_with_tools.side_effect = [
                MockResponse(
                    content="", 
                    tokens_prompt=10, 
                    tokens_completion=10, 
                    model="test-model", 
                    tool_calls=[tool_call]
                ),
                MockResponse(
                    content="Final Answer", 
                    tokens_prompt=10, 
                    tokens_completion=10, 
                    model="test-model", 
                    tool_calls=[]
                )
            ]

            # Mock tools registry
            agent.tools = MagicMock()
            agent.tools.to_ollama_tools.return_value = []
            agent.tools.get_tools_for_tier.return_value = []
            agent.tools.is_tool_available.return_value = True
            
            # Mock the tool itself
            mock_tool = MagicMock()
            mock_tool.name = "read_file"
            # Return 500 chars, which is > context_budget (100)
            large_output = "A" * 500
            mock_tool.function = AsyncMock(return_value=large_output)
            
            agent.tools.get_tool.return_value = mock_tool

            # 2. Execution
            await agent.ask_with_tools("Check this")

            # 3. Verification
            # Check the second call to generate_with_tools
            self.assertEqual(agent.ollama.generate_with_tools.call_count, 2)
            
            # Get arguments of the second call
            call_args = agent.ollama.generate_with_tools.call_args_list[1]
            request = call_args[0][0] # First arg is request object
            
            # Calculate total tokens in messages
            total_tokens = 0
            for msg in request.messages:
                content = msg.get("content")
                if content:
                    total_tokens += len(content)
            
            # Assert failure condition: total tokens > context budget
            # This confirms the gap exists
            self.assertGreater(
                total_tokens, 
                config.agent.context_budget, 
                f"Total tokens {total_tokens} should exceed budget {config.agent.context_budget} to confirm gap"
            )

if __name__ == "__main__":
    unittest.main()
