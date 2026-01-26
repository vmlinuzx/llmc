"""LiteLLM backend for llmc_agent (async interface).

This backend implements the Backend ABC for async agent use cases,
including chat, streaming, and tool calling.

Design: HLD-litellm-migration-FINAL.md Section 4.3
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from llmc.backends.litellm_core import LiteLLMConfig, LiteLLMCore
from llmc_agent.backends.base import Backend, GenerateRequest, GenerateResponse

if TYPE_CHECKING:
    pass


class LiteLLMAgentBackend(Backend):
    """LiteLLM-based backend for llmc_agent.

    Implements the Backend ABC for async agent use cases.
    Supports:
    - Non-streaming generation
    - Streaming generation
    - Tool calling with automatic format normalization
    - Health checks
    
    Example:
        >>> config = LiteLLMConfig(model="ollama_chat/qwen3-next-80b")
        >>> backend = LiteLLMAgentBackend(config)
        >>> response = await backend.generate(request)
    """

    def __init__(self, config: LiteLLMConfig) -> None:
        """Initialize the backend.
        
        Args:
            config: LiteLLM configuration
        """
        self._core = LiteLLMCore(config)
        self._config = config

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a response (non-streaming).
        
        Args:
            request: Generation request with messages, system prompt, etc.
            
        Returns:
            GenerateResponse with content and metadata
            
        Raises:
            BackendError: If the LLM call fails
        """
        from litellm import acompletion

        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        try:
            response = await acompletion(
                messages=messages,
                **self._core.get_common_kwargs(),
            )
        except Exception as e:
            raise self._core.map_exception(e) from e

        return self._to_response(response, request.model)

    async def generate_stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        """Generate a response with streaming.
        
        Args:
            request: Generation request
            
        Yields:
            Content chunks as they arrive
        """
        from litellm import acompletion

        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        kwargs = self._core.get_common_kwargs()
        kwargs["stream"] = True
        # Remove num_retries for streaming (not well-supported by litellm)
        kwargs.pop("num_retries", None)

        response = await acompletion(messages=messages, **kwargs)

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def generate_with_tools(
        self,
        request: GenerateRequest,
        tools: list[dict[str, Any]],
    ) -> GenerateResponse:
        """Generate a response with tool support.
        
        Args:
            request: Generation request
            tools: List of tools in OpenAI format
            
        Returns:
            GenerateResponse with tool_calls populated if model used tools
            
        Raises:
            BackendError: If the LLM call fails
        """
        from litellm import acompletion

        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        kwargs = self._core.get_common_kwargs()
        kwargs["messages"] = messages

        if tools:
            kwargs["tools"] = tools
            if not self._core.should_skip_tool_choice():
                kwargs["tool_choice"] = "auto"

        try:
            response = await acompletion(**kwargs)
        except Exception as e:
            raise self._core.map_exception(e) from e

        return self._to_response(response, request.model)

    async def health_check(self) -> bool:
        """Check if backend is available.
        
        Makes a minimal LLM call to verify connectivity.
        
        Returns:
            True if backend is healthy, False otherwise
        """
        from litellm import acompletion

        try:
            await acompletion(
                model=self._config.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                timeout=5.0,
                api_key=self._config.api_key,
                api_base=self._config.api_base,
            )
            return True
        except Exception:
            return False

    def _to_response(self, response: Any, model_override: str) -> GenerateResponse:
        """Convert LiteLLM response to GenerateResponse.
        
        Args:
            response: LiteLLM ModelResponse object
            model_override: Model name from request (fallback)
            
        Returns:
            GenerateResponse with normalized fields
        """
        choice = response.choices[0]
        message = choice.message
        usage = response.usage

        return GenerateResponse(
            content=message.content or "",
            tokens_prompt=usage.prompt_tokens if usage else 0,
            tokens_completion=usage.completion_tokens if usage else 0,
            model=response.model or model_override,
            finish_reason=choice.finish_reason or "stop",
            tool_calls=self._core.parse_tool_calls(message),
            raw_response=response,
        )


__all__ = ["LiteLLMAgentBackend"]
