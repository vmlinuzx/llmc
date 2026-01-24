"""Test fixtures for RLM tests."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from llmc.rlm.config import RLMConfig


@pytest.fixture
def mock_llm_backend():
    """Mock LLMC backend with canned responses."""
    backend = MagicMock()
    
    # Canned response: code with FINAL
    backend.completion_sync = MagicMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(
            content='```python\nFINAL("The answer is 42")\n```'
        ))],
        usage=MagicMock(prompt_tokens=100, completion_tokens=50),
    ))
    
    backend.completion_async = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(
            content='```python\nFINAL("The answer is 42")\n```'
        ))],
        usage=MagicMock(prompt_tokens=100, completion_tokens=50),
    ))
    
    return backend


@pytest.fixture
def mock_config():
    """Config for deterministic tests."""
    return RLMConfig(
        root_model="mock/model",
        sub_model="mock/model",
        sandbox_backend="process",
        max_session_budget_usd=1.00,
        trace_enabled=True,
    )


@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return '''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Calculator:
    """A simple calculator."""
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b
'''
