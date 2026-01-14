"""Comprehensive validation tests for LiteLLM backend integration.

Phase 3 validation covering:
- Provider-specific behavior (Ollama, OpenAI)
- Streaming functionality
- Tool calling
- Enrichment adapter
- Exception handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from llmc.backends import (
    LiteLLMConfig,
    LiteLLMCore,
    LiteLLMAgentBackend,
    LiteLLMEnrichmentAdapter,
    to_litellm_model,
)
from llmc_agent.backends.base import GenerateRequest, GenerateResponse


# =============================================================================
# Provider-Specific Tests
# =============================================================================

class TestOllamaProvider:
    """Tests specific to Ollama provider behavior."""

    def test_ollama_model_translation(self):
        """Ollama models use ollama_chat prefix for chat endpoint."""
        result = to_litellm_model("ollama", "qwen3-next-80b")
        assert result == "ollama_chat/qwen3-next-80b"

    def test_ollama_skips_tool_choice(self):
        """Ollama models should skip tool_choice to avoid hangs."""
        config = LiteLLMConfig(model="ollama_chat/qwen3")
        core = LiteLLMCore(config)
        assert core.should_skip_tool_choice() is True

    def test_ollama_chat_prefix_skips_tool_choice(self):
        """Any ollama_chat/ prefix should skip tool_choice."""
        for model in ["ollama_chat/llama3", "ollama_chat/mistral", "ollama/gemma"]:
            config = LiteLLMConfig(model=model)
            core = LiteLLMCore(config)
            assert core.should_skip_tool_choice() is True, f"Failed for {model}"

    @pytest.mark.asyncio
    async def test_ollama_generate_with_tools_no_tool_choice(self):
        """Ollama generate_with_tools should NOT include tool_choice."""
        config = LiteLLMConfig(model="ollama_chat/test")
        backend = LiteLLMAgentBackend(config)
        
        request = GenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            model="test",
        )
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test"
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            await backend.generate_with_tools(request, tools)
            
            call_kwargs = mock.call_args.kwargs
            assert "tools" in call_kwargs
            assert "tool_choice" not in call_kwargs  # Key assertion


class TestOpenAIProvider:
    """Tests specific to OpenAI-compatible providers."""

    def test_openai_model_translation(self):
        """OpenAI models use standard prefix."""
        result = to_litellm_model("openai", "gpt-4o")
        assert result == "openai/gpt-4o"

    def test_openai_does_not_skip_tool_choice(self):
        """OpenAI models should include tool_choice."""
        config = LiteLLMConfig(model="openai/gpt-4o")
        core = LiteLLMCore(config)
        assert core.should_skip_tool_choice() is False

    def test_openai_with_custom_api_base(self):
        """OpenAI-compat with custom endpoint (llama.cpp, vLLM)."""
        config = LiteLLMConfig(
            model="openai/local-model",
            api_base="http://localhost:8080/v1",
        )
        core = LiteLLMCore(config)
        
        kwargs = core.get_common_kwargs()
        assert kwargs["api_base"] == "http://localhost:8080/v1"
        assert core.describe_host() == "http://localhost:8080/v1"

    def test_openai_api_key_passed(self):
        """API key should be included in kwargs when set."""
        config = LiteLLMConfig(
            model="openai/gpt-4o",
            api_key="sk-test-key",
        )
        core = LiteLLMCore(config)
        
        kwargs = core.get_common_kwargs()
        assert kwargs["api_key"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_openai_generate_with_tools_includes_tool_choice(self):
        """OpenAI generate_with_tools should include tool_choice=auto."""
        config = LiteLLMConfig(model="openai/gpt-4o")
        backend = LiteLLMAgentBackend(config)
        
        request = GenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            model="test",
        )
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test"
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            await backend.generate_with_tools(request, tools)
            
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs.get("tool_choice") == "auto"


class TestOtherProviders:
    """Tests for other provider translations."""

    def test_groq_native_routing(self):
        """Groq uses native groq/ prefix."""
        result = to_litellm_model("groq", "llama3-70b-8192")
        assert result == "groq/llama3-70b-8192"

    def test_anthropic_standard(self):
        """Anthropic uses standard prefix."""
        result = to_litellm_model("anthropic", "claude-3-haiku-20240307")
        assert result == "anthropic/claude-3-haiku-20240307"

    def test_gemini_standard(self):
        """Gemini uses standard prefix."""
        result = to_litellm_model("gemini", "gemini-1.5-flash")
        assert result == "gemini/gemini-1.5-flash"


# =============================================================================
# Streaming Tests
# =============================================================================

class TestStreaming:
    """Tests for streaming functionality."""

    @pytest.fixture
    def backend(self):
        config = LiteLLMConfig(model="ollama_chat/test")
        return LiteLLMAgentBackend(config)

    @pytest.fixture
    def gen_request(self):
        return GenerateRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            model="test",
        )

    @pytest.mark.asyncio
    async def test_streaming_yields_content(self, backend, gen_request):
        """Streaming should yield content chunks."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_stream()
            
            chunks = []
            async for chunk in backend.generate_stream(gen_request):
                chunks.append(chunk)
            
            assert chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_streaming_skips_empty_content(self, backend, gen_request):
        """Streaming should skip chunks with None content."""
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hi"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_stream()
            
            chunks = []
            async for chunk in backend.generate_stream(gen_request):
                chunks.append(chunk)
            
            assert chunks == ["Hi", "!"]

    @pytest.mark.asyncio
    async def test_streaming_removes_num_retries(self, backend, gen_request):
        """Streaming should remove num_retries from kwargs."""
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="x"))])

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_stream()
            
            async for _ in backend.generate_stream(gen_request):
                pass
            
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs.get("stream") is True
            assert "num_retries" not in call_kwargs


# =============================================================================
# Tool Calling Tests
# =============================================================================

class TestToolCalling:
    """Tests for tool calling functionality."""

    def test_parse_tool_calls_single(self):
        """Should parse a single tool call."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        mock_tc = MagicMock()
        mock_tc.function.name = "search_code"
        mock_tc.function.arguments = '{"query": "auth"}'
        mock_tc.id = "call_123"
        
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tc]
        
        result = core.parse_tool_calls(mock_message)
        
        assert len(result) == 1
        assert result[0]["function"]["name"] == "search_code"
        assert result[0]["function"]["arguments"] == '{"query": "auth"}'
        assert result[0]["id"] == "call_123"
        assert result[0]["type"] == "function"

    def test_parse_tool_calls_multiple(self):
        """Should parse multiple tool calls."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        mock_tc1 = MagicMock()
        mock_tc1.function.name = "read_file"
        mock_tc1.function.arguments = '{"path": "foo.py"}'
        mock_tc1.id = "call_1"
        
        mock_tc2 = MagicMock()
        mock_tc2.function.name = "write_file"
        mock_tc2.function.arguments = '{"path": "bar.py", "content": "x"}'
        mock_tc2.id = "call_2"
        
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tc1, mock_tc2]
        
        result = core.parse_tool_calls(mock_message)
        
        assert len(result) == 2
        assert result[0]["function"]["name"] == "read_file"
        assert result[1]["function"]["name"] == "write_file"

    def test_parse_tool_calls_empty(self):
        """Should return empty list when no tool calls."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        mock_message = MagicMock()
        mock_message.tool_calls = None
        
        result = core.parse_tool_calls(mock_message)
        assert result == []

    @pytest.mark.asyncio
    async def test_response_includes_tool_calls(self):
        """Response should include parsed tool calls."""
        config = LiteLLMConfig(model="openai/gpt-4o")
        backend = LiteLLMAgentBackend(config)
        
        request = GenerateRequest(
            messages=[{"role": "user", "content": "Search for auth"}],
            system="You are helpful",
            model="test",
        )
        tools = [{"type": "function", "function": {"name": "search"}}]
        
        mock_tc = MagicMock()
        mock_tc.function.name = "search"
        mock_tc.function.arguments = '{"q": "auth"}'
        mock_tc.id = "call_xyz"
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].message.tool_calls = [mock_tc]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4o"
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            
            response = await backend.generate_with_tools(request, tools)
            
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "search"
            assert response.finish_reason == "tool_calls"


# =============================================================================
# Enrichment Adapter Tests
# =============================================================================

class TestEnrichmentAdapter:
    """Tests for sync enrichment adapter."""

    def test_generate_returns_tuple(self):
        """generate() should return (result, meta) tuple."""
        config = LiteLLMConfig(model="ollama_chat/test")
        adapter = LiteLLMEnrichmentAdapter(config)
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "Test code"}'
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
        mock_response.model = "test-model"
        
        with patch("litellm.completion") as mock:
            mock.return_value = mock_response
            
            result, meta = adapter.generate("Analyze this", item={"id": 1})
            
            assert isinstance(result, dict)
            assert isinstance(meta, dict)
            assert result["summary"] == "Test code"
            assert meta["prompt_tokens"] == 50

    def test_json_parsing_code_fence(self):
        """Should parse JSON from code fence."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = '''Here's my analysis:
```json
{"summary": "Auth module", "key_topics": ["jwt", "oauth"]}
```
'''
        result = core.parse_enrichment_json(text)
        assert result["summary"] == "Auth module"
        assert "jwt" in result["key_topics"]

    def test_json_parsing_bare(self):
        """Should parse bare JSON."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = 'The result is {"summary": "DB layer", "complexity": "high"}'
        result = core.parse_enrichment_json(text)
        assert result["summary"] == "DB layer"

    def test_json_parsing_fallback(self):
        """Should fallback when no JSON found."""
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        text = "This code handles authentication"
        result = core.parse_enrichment_json(text)
        assert result["summary"] == "This code handles authentication"
        assert result["complexity"] == "unknown"

    def test_circuit_breaker_blocks_when_open(self):
        """Should raise when circuit breaker is open."""
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        cb = MagicMock()
        cb.can_proceed.return_value = False
        
        adapter = LiteLLMEnrichmentAdapter(config, circuit_breaker=cb)
        
        with pytest.raises(BackendError) as exc:
            adapter.generate("test", item={})
        
        assert "Circuit breaker open" in str(exc.value)

    def test_circuit_breaker_records_success(self):
        """Should record success on circuit breaker."""
        config = LiteLLMConfig(model="test")
        cb = MagicMock()
        cb.can_proceed.return_value = True
        
        adapter = LiteLLMEnrichmentAdapter(config, circuit_breaker=cb)
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "x"}'
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "test"
        
        with patch("litellm.completion") as mock:
            mock.return_value = mock_response
            adapter.generate("test", item={})
        
        cb.record_success.assert_called_once()

    def test_circuit_breaker_records_failure(self):
        """Should record failure on circuit breaker when exception."""
        config = LiteLLMConfig(model="test")
        cb = MagicMock()
        cb.can_proceed.return_value = True
        
        adapter = LiteLLMEnrichmentAdapter(config, circuit_breaker=cb)
        
        with patch("litellm.completion") as mock:
            mock.side_effect = Exception("API Error")
            
            with pytest.raises(Exception):
                adapter.generate("test", item={})
        
        cb.record_failure.assert_called_once()


# =============================================================================
# Exception Mapping Tests
# =============================================================================

class TestExceptionMapping:
    """Tests for LiteLLM exception mapping."""

    def test_rate_limit_error(self):
        """Should map RateLimitError to rate_limit failure_type."""
        from litellm.exceptions import RateLimitError
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = RateLimitError("Rate limited", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "rate_limit"

    def test_timeout_error(self):
        """Should map Timeout to timeout failure_type."""
        from litellm.exceptions import Timeout
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = Timeout("Timed out", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "timeout"

    def test_auth_error(self):
        """Should map AuthenticationError to auth_error failure_type."""
        from litellm.exceptions import AuthenticationError
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = AuthenticationError("Bad key", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "auth_error"

    def test_service_unavailable(self):
        """Should map ServiceUnavailableError to server_error failure_type."""
        from litellm.exceptions import ServiceUnavailableError
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = ServiceUnavailableError("Server down", llm_provider="openai", model="gpt-4")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "server_error"

    def test_generic_exception(self):
        """Should map unknown exceptions to backend_error."""
        from llmc.rag.enrichment_backends import BackendError
        
        config = LiteLLMConfig(model="test")
        core = LiteLLMCore(config)
        
        exc = ValueError("Unknown error")
        mapped = core.map_exception(exc)
        
        assert isinstance(mapped, BackendError)
        assert mapped.failure_type == "backend_error"
