import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from llmc_agent.agent import Agent
from llmc_agent.config import Config
from llmc_agent.backends.base import GenerateResponse
from llmc_agent.tools import ToolTier

@pytest.mark.allow_network
def test_agent_handles_malformed_json_tool_args():
    """
    Test that the agent handles invalid JSON in tool arguments gracefully.
    It should catch the JSONDecodeError and report it back to the model
    as a tool error message.
    """
    import asyncio
    asyncio.run(_test_impl())

async def _test_impl():
    # 1. Setup
    # Create a mock config
    config = MagicMock(spec=Config)
    config.ollama = MagicMock()
    config.ollama.url = "http://mock"
    config.ollama.timeout = 10
    config.ollama.temperature = 0.0
    config.ollama.num_ctx = 100
    
    # Disable RAG to simplify
    config.rag = MagicMock()
    config.rag.enabled = False
    
    config.agent = MagicMock()
    config.agent.model = "mock-model"
    config.agent.context_budget = 1000
    config.agent.response_reserve = 100
    
    # Initialize agent
    agent = Agent(config)
    
    # Mock the backend
    mock_backend = AsyncMock()
    agent.ollama = mock_backend
    
    # 2. Execution
    # Define the malformed tool call
    # "read_file" is a valid tool in the registry (Tier 1)
    # "{ unquoted_key: 5 }" is invalid JSON (keys must be quoted)
    malformed_tool_call = {
        "function": {
            "name": "read_file",
            "arguments": "{ unquoted_key: 5 }" 
        },
        "id": "call_123"
    }
    
    # Response 1: Triggers the error
    response_1 = GenerateResponse(
        content="I will read the file.",
        tokens_prompt=10,
        tokens_completion=10,
        model="mock",
        finish_reason="tool_calls",
        tool_calls=[malformed_tool_call]
    )
    
    # Response 2: Completes the interaction
    response_2 = GenerateResponse(
        content="Sorry, I made a mistake with the JSON.",
        tokens_prompt=10,
        tokens_completion=10,
        model="mock",
        finish_reason="stop",
        tool_calls=[]
    )
    
    mock_backend.generate_with_tools.side_effect = [response_1, response_2]
    
    # Call ask_with_tools
    # "read" is a keyword to unlock WALK tier (where read_file is available)
    await agent.ask_with_tools("read this file", max_tool_rounds=2)
    
    # 3. Verification
    # Verify that generate_with_tools was called twice
    assert mock_backend.generate_with_tools.call_count == 2
    
    # Inspect the arguments of the second call to see what the agent sent back
    second_call_args = mock_backend.generate_with_tools.call_args_list[1]
    request = second_call_args[0][0]  # args[0] is the request object
    
    # The last message in the request history should be the tool error
    last_message = request.messages[-1]
    
    # Verify structure
    assert last_message["role"] == "tool"
    assert last_message["tool_call_id"] == "call_123"
    
    # Verify content
    error_content = json.loads(last_message["content"])
    assert "error" in error_content
    
    # The error string from json.loads usually mentions "Expecting property name"
    # or similar syntax error details.
    error_msg = error_content["error"]
    print(f"Captured error message: {error_msg}")
    
    # Broad assertion to catch standard JSON errors
    assert any(x in error_msg for x in ["Expecting property name", "JSON", "syntax", "format", "delimited"]) or len(error_msg) > 0
