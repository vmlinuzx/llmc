"""Ollama backend for llmc_agent.

Handles communication with local Ollama server for LLM inference.
"""

# DEPRECATED - See llmc.backends.LiteLLMAgentBackend


from __future__ import annotations

from collections.abc import AsyncIterator
import json

import httpx

from llmc_agent.backends.base import Backend, GenerateRequest, GenerateResponse


class OllamaBackend(Backend):
    """Ollama LLM backend."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        temperature: float = 0.7,
        num_ctx: int = 8192,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_options = {
            "temperature": temperature,
            "num_ctx": num_ctx,
        }

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a response (non-streaming)."""

        # Build messages in Ollama format
        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": {
                **self.default_options,
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return GenerateResponse(
            content=data["message"]["content"],
            tokens_prompt=data.get("prompt_eval_count", 0),
            tokens_completion=data.get("eval_count", 0),
            model=data.get("model", request.model),
            finish_reason="stop" if data.get("done", False) else "unknown",
        )

    async def generate_stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        """Generate a response with streaming."""

        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "options": {
                **self.default_options,
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue

    async def generate_with_tools(
        self,
        request: GenerateRequest,
        tools: list[dict],
    ) -> GenerateResponse:
        """Generate a response with tool support.

        Args:
            request: The generation request
            tools: List of tools in Ollama format

        Returns:
            GenerateResponse with tool_calls populated if model used tools
        """

        # Build messages in Ollama format
        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": {
                **self.default_options,
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
        }

        # Add tools if provided AND model supports native tool calling
        # Models using XML tool format (like custom modelfiles) don't want this
        # The UTP parser will handle tool calls from content instead
        if tools:
            # Check if model likely supports native tools
            model_name = request.model.lower()
            
            # Models with '-tools' suffix always have tool templates
            has_tool_template = '-tools' in model_name
            
            # Known model families that support native tools when properly templated
            native_tool_models = ['llama3', 'mistral', 'qwen2', 'qwen3']
            is_native_family = any(m in model_name for m in native_tool_models)
            
            # 'nothink' modelfiles typically strip tool templates for faster inference
            has_no_tool_template = 'nothink' in model_name
            
            supports_native_tools = has_tool_template or (is_native_family and not has_no_tool_template)
            
            if supports_native_tools:
                payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # Extract tool calls if present
        message = data.get("message", {})
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")

        # Determine finish reason
        if tool_calls:
            finish_reason = "tool_calls"
        elif data.get("done", False):
            finish_reason = "stop"
        else:
            finish_reason = "unknown"

        return GenerateResponse(
            content=content,
            tokens_prompt=data.get("prompt_eval_count", 0),
            tokens_completion=data.get("eval_count", 0),
            model=data.get("model", request.model),
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=data,  # Full response for UTP parser
        )

    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
