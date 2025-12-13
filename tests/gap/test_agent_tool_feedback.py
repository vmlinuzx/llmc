import unittest
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from llmc_agent.agent import Agent
from llmc_agent.tools import ToolTier
from llmc_agent.backends.base import GenerateResponse, GenerateRequest
from llmc_agent.config import Config

@pytest.mark.allow_network
class TestAgentToolFeedback(unittest.IsolatedAsyncioTestCase):
    async def test_silent_tool_failure_feedback(self):
        """
        Test that the agent provides feedback when a tool is not available in the current tier.
        SDD: tests/gap/SDDs/SDD-Agent-SilentToolFailure.md
        """
        # Setup Config
        mock_config = MagicMock()
        mock_config.ollama.url = "http://localhost:11434"
        mock_config.ollama.timeout = 30
        mock_config.ollama.temperature = 0.0
        mock_config.ollama.num_ctx = 4096
        mock_config.rag.enabled = False
        mock_config.agent.model = "test-model"
        mock_config.agent.context_budget = 8192
        mock_config.agent.response_reserve = 1024
        mock_config.rag.include_summary = True
        mock_config.rag.max_results = 5
        mock_config.rag.min_score = 0.5

        # Mock OllamaBackend
        with patch('llmc_agent.agent.OllamaBackend') as MockOllamaBackend:
            mock_backend_instance = AsyncMock()
            MockOllamaBackend.return_value = mock_backend_instance
            
            # Instantiate Agent
            agent = Agent(mock_config)
            
            # Force ToolRegistry to WALK tier
            agent.tools.current_tier = ToolTier.WALK
            
            # Mock responses
            # Response 1: Tool call to 'write_file' (RUN tier)
            tool_call_args = '{"path": "test.txt", "content": "hello"}'
            response_1 = GenerateResponse(
                content="",
                tokens_prompt=10,
                tokens_completion=10,
                model="test-model",
                finish_reason="tool_calls",
                tool_calls=[{
                    "function": {
                        "name": "write_file",
                        "arguments": tool_call_args
                    },
                    "id": "call_123"
                }]
            )
            
            # Response 2: Text response (simulating model reacting to feedback)
            response_2 = GenerateResponse(
                content="I see I cannot write files.",
                tokens_prompt=20,
                tokens_completion=10,
                model="test-model",
                finish_reason="stop",
                tool_calls=[]
            )
            
            # We might need more responses if it loops multiple times due to failure
            mock_backend_instance.generate_with_tools.side_effect = [response_1, response_2, response_2, response_2]
            
            # Patch detect_intent_tier to prevent auto-upgrade to RUN
            with patch('llmc_agent.tools.detect_intent_tier', return_value=ToolTier.WALK):
                await agent.ask_with_tools("Please write this file")
            
            # Assertions
            
            # Check the inputs to the second call
            # We expect at least 2 calls. If the agent silently failed and looped, it might have called more times 
            # with the exact same input (missing tool feedback).
            assert mock_backend_instance.generate_with_tools.call_count >= 2
            
            # Get the arguments of the second call
            second_call_request = mock_backend_instance.generate_with_tools.call_args_list[1][0][0]
            messages = second_call_request.messages
            
            # Verify that we have a tool error message
            
            has_assistant_call = any(
                msg.get("role") == "assistant" and msg.get("tool_calls") 
                for msg in messages
            )
            
            assert has_assistant_call, "Assistant tool call message missing from history (Silent Failure detected)"
            
            error_msg = next(
                (msg for msg in messages if msg.get("role") == "tool" and "not available in current tier" in str(msg.get("content"))),
                None
            )
            
            assert error_msg is not None, "Expected error message about unavailable tool not found in messages."
            assert "WALK" in error_msg["content"], "Error message should mention the current tier (WALK)."