import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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
    # 1st response: Use nav_info()
    # 2nd response: FINAL answer
    
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

    # 3rd response to catch failure loop
    mock_response_3 = MagicMock()
    mock_response_3.choices = [MagicMock(message=MagicMock(content="""
I am stuck.
```python
FINAL("stuck")
```
"""))]
    mock_response_3.usage.prompt_tokens = 10
    mock_response_3.usage.completion_tokens = 10

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        result = await session.run("Analyze the code")
        
        if not result.success:
             print("\nSESSION TRACE:")
             for event in session.trace:
                 print(event)
        
        assert result.success
        assert result.answer is not None
        # nav_info should return a dict with language='python'
        assert "python" in str(result.answer)
        
        # Verify trace shows interception
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
    
    # Response with bare call
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock(message=MagicMock(content="""
```python
nav_info()
```
"""))]
    mock_response_1.usage.prompt_tokens = 10
    mock_response_1.usage.completion_tokens = 10
    
    # Response fixing it
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

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        result = await session.run("Test bare call")
        
        if not result.success:
             print("\nSESSION TRACE:")
             for event in session.trace:
                 print(event)
                 
        assert result.success
        
        # Check that we sent feedback about the error
        # The 2nd call to acompletion should contain the error message in 'messages'
        # call_args_list[1] is the 2nd call (fixing it), based on messages from 1st call
        call_args_2 = mock_acompletion.call_args_list[1]
        messages_2 = call_args_2.kwargs['messages']
        last_user_msg = messages_2[-1]['content']
        
        assert "Execution results" in last_user_msg
        assert "Tool calls must be assigned" in last_user_msg
