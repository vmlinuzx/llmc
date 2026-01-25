import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import contextlib

# Fixture to mock litellm if missing
@pytest.fixture(autouse=True)
def mock_litellm_dependency():
    """Ensure litellm is available (mocked) for these tests."""
    with patch.dict(sys.modules):
        if "litellm" not in sys.modules:
            sys.modules["litellm"] = MagicMock()
        yield

from llmc.rlm.session import RLMSession, RLMConfig

@pytest.mark.asyncio
async def test_callback_interception_end_to_end(sample_python_code):
    """Verify that x = nav_info() is intercepted and executed without hitting sandbox callback stub."""
    
    # Config: use process backend
    config = RLMConfig(
        root_model="mock/root",
        sub_model="mock/sub",
        sandbox_backend="process",
        max_tokens_per_session=10000,
        max_session_budget_usd=1.0,
        code_timeout_seconds=5,
        trace_enabled=True,
    )
    
    session = RLMSession(config)
    session.load_code_context(sample_python_code)
    
    # Mock litellm.acompletion to return a response that uses nav_info()
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock(message=MagicMock(content="""
I'll check the code structure.
```python
info = nav_info()
```
"""))]
    mock_response_1.usage.prompt_tokens = 10
    mock_response_1.usage.completion_tokens = 10

    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock(message=MagicMock(content="""
Okay, I see the info.
```python
FINAL(info['language'])
```
"""))]
    mock_response_2.usage.prompt_tokens = 10
    mock_response_2.usage.completion_tokens = 10

    mock_response_3 = MagicMock()
    mock_response_3.choices = [MagicMock(message=MagicMock(content="""
I am stuck.
```python
FINAL("stuck")
```
"""))]
    mock_response_3.usage.prompt_tokens = 10
    mock_response_3.usage.completion_tokens = 10

    # We patch litellm.acompletion.
    # Note: RLMSession imports litellm inside run().
    # If litellm is mocked in sys.modules, import litellm returns the mock.
    # We need to set the attribute on THAT mock.
    
    import litellm
    with patch.object(litellm, "acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        result = await session.run("Analyze the code")
        
        if not result.success:
             print("\nSESSION TRACE:")
             for event in session.trace:
                 print(event)
        
        assert result.success
        assert result.answer is not None
        assert "python" in str(result.answer)
        
        intercept_events = [e for e in session.trace if e["event"] == "tool_intercepted"]
        assert len(intercept_events) == 1
        assert intercept_events[0]["tool"] == "nav_info"

@pytest.mark.asyncio
async def test_interception_rejects_bare_calls():
    """Verify that bare calls are rejected and feedback is provided."""
    config = RLMConfig(
        root_model="mock/root",
        sub_model="mock/sub",
        sandbox_backend="process",
        trace_enabled=True,
    )
    session = RLMSession(config)
    session.load_code_context("pass")
    
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock(message=MagicMock(content="""
```python
nav_info()
```
"""))]
    mock_response_1.usage.prompt_tokens = 10
    mock_response_1.usage.completion_tokens = 10
    
    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock(message=MagicMock(content="""
Ah, I need to assign it.
```python
x = nav_info()
FINAL(x)
```
"""))]
    mock_response_2.usage.prompt_tokens = 10
    mock_response_2.usage.completion_tokens = 10
    
    mock_response_3 = MagicMock()
    mock_response_3.choices = [MagicMock(message=MagicMock(content="""
Stuck.
```python
FINAL("stuck")
```
"""))]
    mock_response_3.usage.prompt_tokens = 10
    mock_response_3.usage.completion_tokens = 10

    import litellm
    with patch.object(litellm, "acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        result = await session.run("Test bare call")
        
        if not result.success:
             print("\nSESSION TRACE:")
             for event in session.trace:
                 print(event)
                 
        assert result.success
        
        call_args_2 = mock_acompletion.call_args_list[1]
        messages_2 = call_args_2.kwargs['messages']
        last_user_msg = messages_2[-1]['content']
        
        assert "Execution results" in last_user_msg
        assert "Tool calls must be assigned" in last_user_msg
