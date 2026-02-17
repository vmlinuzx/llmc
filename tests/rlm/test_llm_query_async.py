"""Test that llm_query uses async litellm.acompletion and does not block."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_litellm_dependency():
    """Ensure litellm is available (mocked) for these tests."""
    with patch.dict(sys.modules):
        if "litellm" not in sys.modules:
            sys.modules["litellm"] = MagicMock()
        yield


from llmc.rlm.session import RLMConfig, RLMSession


@pytest.mark.asyncio
async def test_llm_query_uses_async_acompletion(sample_python_code):
    """Verify llm_query uses litellm.acompletion (not completion) and is awaitable.
    
    This test ensures:
    1. The llm_query tool is async and returns an awaitable
    2. litellm.completion is NOT called (only litellm.acompletion)
    3. Sub-calls use model=config.sub_model
    4. The orchestration loop properly awaits async tool results
    """
    config = RLMConfig(
        root_model="mock/root",
        sub_model="mock/sub",
        sandbox_backend="process",
        max_tokens_per_session=10000,
        max_session_budget_usd=1.0,
        code_timeout_seconds=5,
        max_turns=3,
        trace_enabled=True,
    )
    
    session = RLMSession(config)
    session.load_code_context(sample_python_code)
    
    mock_response_root = MagicMock()
    mock_response_root.choices = [MagicMock(message=MagicMock(content="""
I'll use llm_query for sub-analysis.
```python
answer = llm_query("What is the main function?")
```
"""))]
    mock_response_root.usage.prompt_tokens = 10
    mock_response_root.usage.completion_tokens = 20
    
    mock_response_sub = MagicMock()
    mock_response_sub.choices = [MagicMock(message=MagicMock(content="""
The main function is main() at line 2.
"""))]
    mock_response_sub.usage.prompt_tokens = 5
    mock_response_sub.usage.completion_tokens = 10
    
    mock_response_final = MagicMock()
    mock_response_final.choices = [MagicMock(message=MagicMock(content="""
Final answer.
```python
FINAL("main at line 2")
```
"""))]
    mock_response_final.usage.prompt_tokens = 10
    mock_response_final.usage.completion_tokens = 15
    
    import litellm
    call_tracker = []
    
    async def mock_acompletion_async(*args, **kwargs):
        call_tracker.append(("acompletion", kwargs.get("model")))
        if len(call_tracker) == 1:
            return mock_response_root
        elif len(call_tracker) == 2:
            return mock_response_sub
        else:
            return mock_response_final
    
    with patch.object(litellm, "acompletion", new=mock_acompletion_async):
        result = await session.run("Analyze the code")
    
    assert result.success, f"Session failed: {result.error}"
    assert result.answer == "main at line 2"
    
    assert len(call_tracker) == 3, f"Expected 3 calls, got {len(call_tracker)}"
    
    assert call_tracker[0] == ("acompletion", "mock/root"), f"Root call should use root model, got {call_tracker[0]}"
    assert call_tracker[1] == ("acompletion", "mock/sub"), f"Sub call should use sub model, got {call_tracker[1]}"
    assert call_tracker[2] == ("acompletion", "mock/root"), f"Final call should use root model, got {call_tracker[2]}"
    
    assert not any(c[0] == "completion" for c in call_tracker), \
        "litellm.completion should not be called"
    
    sub_calls = [e for e in session.trace if e["event"] == "sub_call"]
    assert len(sub_calls) >= 1, "Expected at least one sub_call in trace"
    assert sub_calls[0]["prompt_preview"].startswith("What is the main function?")
