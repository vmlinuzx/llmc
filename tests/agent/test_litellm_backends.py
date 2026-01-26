"""Tests for LiteLLM backend implementations.

Tests cover:
- LiteLLMConfig construction
- LiteLLMCore shared logic
- LiteLLMAgentBackend (async)
- LiteLLMEnrichmentAdapter (sync)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmc.backends import (
    LiteLLMAgentBackend,
    LiteLLMConfig,
    LiteLLMCore,
    LiteLLMEnrichmentAdapter,
    to_litellm_model,
)
from llmc_agent.backends.base import GenerateRequest, GenerateResponse


class TestLiteLLMConfig:
    """Test LiteLLMConfig dataclass."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = LiteLLMConfig(model="ollama_chat/test")
        
        assert config.model == "ollama_chat/test"
        assert config.api_key is None
        assert config.api_base is None
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.timeout == 120.0
        assert config.num_retries == 3
        assert config.drop_params is True

    def test_custom_values(self):
        """Config should accept custom values."""
        config = LiteLLMConfig(
            model="openai/gpt-4o",
            api_key="sk-test",
            api_base="https://custom.api",
            temperature=0.5,
            max_tokens=2048,
            timeout=60.0,
            num_retries=5,
        )
        
        assert config.model == "openai/gpt-4o"
        assert config.api_key == "sk-test"
        assert config.api_base == "https://custom.api"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


class TestToLiteLLMModel:
    """Test model name conversion function."""

    def test_ollama_uses_chat_endpoint(self):
        """Ollama should use ollama_chat prefix for multi-turn support."""
        result = to_litellm_model("ollama", "qwen3-next-80b")
        assert result == "ollama_chat/qwen3-next-80b"

    def test_groq_native_routing(self):
        """Groq should use native prefix."""
        result = to_litellm_model("groq", "llama3-70b-8192")
        assert result == "groq/llama3-70b-8192"

    def test_openai_standard(self):
        """OpenAI should use standard prefix."""
        result = to_litellm_model("openai", "gpt-4o")
        assert result == "openai/gpt-4o"

    def test_anthropic_standard(self):
        """Anthropic should use standard prefix."""
        result = to_litellm_model("anthropic", "claude-3-haiku-20240307")
        assert result == "anthropic/claude-3-haiku-20240307"


class TestLiteLLMCore:
    """Test shared LiteLLMCore logic."""

    def test_get_common_kwargs(self):
        """Should return common kwargs for litellm calls."""
        config = LiteLLMConfig(
            model="ollama_chat/test",
            api_key="test-key",
            api_base="http://localhost:8080",
        )
        core = LiteLLMCore(config)
        kwargs = core.get_common_kwargs()
        
        assert kwargs["model"] == "ollama_chat/test"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 1024
        assert kwargs["api_key"] == "test-key"
        assert kwargs["api_base"] == "http://localhost:8080"

    def test_get_common_kwargs_no_api_key(self):
        """Should omit None values."""
        config = LiteLLMConfig(model="ollama_chat/test")
        core = LiteLLMCore(config)
        kwargs = core.get_common_kwargs()
        
        assert "api_key" not in kwargs
        assert "api_base" not in kwargs

    def test_should_skip_tool_choice_ollama(self):
        """Ollama models should skip tool_choice."""
        config = LiteLLMConfig(model="ollama_chat/qwen3")
        core = LiteLLMCore(config)
        
        assert core.should_skip_tool_choice() is True

    def test_should_skip_tool_choice_openai(self):
        """OpenAI models should not skip tool_choice."""
        config = LiteLLMConfig(model="openai/gpt-4o")
        core = LiteLLMCore(config)
        
        assert core.should_skip_tool_choice() is False

    def test_describe_host_with_api_base(self):
        """Should return api_base when set."""
        config = LiteLLMConfig(
            model="openai/gpt-oss",
            api_base="http://localhost:8080",
        )
        core = LiteLLMCore(config)
        
        assert core.describe_host() == "http://localhost:8080"

    def test_describe_host_from_provider(self):
        """Should extract provider from model when no api_base."""
        config = LiteLLMConfig(model="anthropic/claude-3")
        core = LiteLLMCore(config)
        
        assert core.describe_host() == "anthropic API"

    def test_parse_enrichment_json_fenced(self):
        """Should parse JSON from code fence."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = '''Here's the analysis:
```json
{"summary": "Test summary", "key_topics": ["a", "b"]}
```
'''
        result = core.parse_enrichment_json(text)
        
        assert result["summary"] == "Test summary"
        assert result["key_topics"] == ["a", "b"]

    def test_parse_enrichment_json_bare(self):
        """Should parse bare JSON object."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = 'Result: {"summary": "Test", "complexity": "low"}'
        result = core.parse_enrichment_json(text)
        
        assert result["summary"] == "Test"
        assert result["complexity"] == "low"

    def test_parse_enrichment_json_fallback(self):
        """Should fallback to text summary if no JSON."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = "This is just plain text without JSON"
        result = core.parse_enrichment_json(text)
        
        assert result["summary"] == "This is just plain text without JSON"
        assert result["key_topics"] == []
        assert result["complexity"] == "unknown"

    def test_parse_tool_calls(self):
        """Should normalize tool calls to OpenAI format."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        # Mock message with tool_calls
        mock_tc = MagicMock()
        mock_tc.function.name = "search"
        mock_tc.function.arguments = '{"query": "test"}'
        mock_tc.id = "call_123"
        
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tc]
        
        result = core.parse_tool_calls(mock_message)
        
        assert len(result) == 1
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["arguments"] == '{"query": "test"}'
        assert result[0]["id"] == "call_123"
        assert result[0]["type"] == "function"

    def test_parse_tool_calls_empty(self):
        """Should handle messages without tool calls."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        mock_message = MagicMock()
        mock_message.tool_calls = None
        
        result = core.parse_tool_calls(mock_message)
        assert result == []


class TestLiteLLMAgentBackend:
    """Test async agent backend."""

    @pytest.fixture
    def backend(self):
        """Create a test backend."""
        config = LiteLLMConfig(model="ollama_chat/test")
        return LiteLLMAgentBackend(config)

    @pytest.fixture
    def gen_request(self):
        """Create a test request."""
        return GenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant",
            model="test",
        )

    @pytest.mark.asyncio
    async def test_generate_success(self, backend, gen_request):
        """Should call acompletion and return response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test-model"
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            
            response = await backend.generate(gen_request)
            
            assert isinstance(response, GenerateResponse)
            assert response.content == "Hello!"
            assert response.tokens_prompt == 10
            assert response.tokens_completion == 5
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_with_tools(self, backend, gen_request):
        """Should include tools in request when provided."""
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test"
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            
            await backend.generate_with_tools(gen_request, tools)
            
            # Check tools were passed
            call_kwargs = mock_acomp.call_args.kwargs
            assert call_kwargs.get("tools") == tools
            # Ollama should skip tool_choice
            assert "tool_choice" not in call_kwargs

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        """Should return True when healthy."""
        mock_response = MagicMock()
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            
            result = await backend.health_check()
            
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, backend):
        """Should return False when unhealthy."""
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.side_effect = Exception("Connection failed")
            
            result = await backend.health_check()
            
            assert result is False


class TestLiteLLMEnrichmentAdapter:
    """Test sync enrichment adapter."""

    @pytest.fixture
    def adapter(self):
        """Create a test adapter."""
        config = LiteLLMConfig(model="ollama_chat/test")
        return LiteLLMEnrichmentAdapter(config)

    def test_config_property(self, adapter):
        """Should expose config for BackendAdapter Protocol."""
        assert adapter.config.model == "ollama_chat/test"

    def test_describe_host(self, adapter):
        """Should describe host."""
        assert "ollama" in adapter.describe_host().lower()

    def test_generate_success(self, adapter):
        """Should call completion and return parsed result."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "Test", "key_topics": []}'
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
        mock_response.model = "test-model"
        
        with patch("litellm.completion") as mock_comp:
            mock_comp.return_value = mock_response
            
            result, meta = adapter.generate("Test prompt", item={"id": 1})
            
            assert result["summary"] == "Test"
            assert meta["prompt_tokens"] == 50
            assert meta["completion_tokens"] == 20
            assert meta["model"] == "test-model"

    def test_generate_with_circuit_breaker(self):
        """Should check circuit breaker before calling."""
        from llmc.rag.enrichment_reliability import CircuitBreaker
        
        config = LiteLLMConfig(model="ollama_chat/test")
        cb = MagicMock(spec=CircuitBreaker)
        cb.can_proceed.return_value = False
        
        adapter = LiteLLMEnrichmentAdapter(config, circuit_breaker=cb)
        
        with pytest.raises(Exception) as exc_info:
            adapter.generate("Test", item={})
        
        assert "Circuit breaker open" in str(exc_info.value)

    def test_generate_records_circuit_breaker_success(self):
        """Should record success on circuit breaker."""
        from llmc.rag.enrichment_reliability import CircuitBreaker
        
        config = LiteLLMConfig(model="ollama_chat/test")
        cb = MagicMock(spec=CircuitBreaker)
        cb.can_proceed.return_value = True
        
        adapter = LiteLLMEnrichmentAdapter(config, circuit_breaker=cb)
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "Test"}'
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test"
        
        with patch("litellm.completion") as mock_comp:
            mock_comp.return_value = mock_response
            adapter.generate("Test", item={})
        
        cb.record_success.assert_called_once()


class TestExceptionMapping:
    """Test exception mapping from LiteLLM to BackendError."""

    def test_rate_limit_error(self):
        """Should map RateLimitError correctly."""
        from litellm.exceptions import RateLimitError

        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = RateLimitError("Rate limited", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "rate_limit"

    def test_timeout_error(self):
        """Should map Timeout correctly."""
        from litellm.exceptions import Timeout

        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = Timeout("Request timed out", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "timeout"

    def test_generic_exception(self):
        """Should map unknown exceptions to backend_error."""
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = ValueError("Unknown error")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "backend_error"
