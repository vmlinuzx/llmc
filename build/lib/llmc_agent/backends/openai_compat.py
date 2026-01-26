"""OpenAI-compatible backend for llmc_agent.

Works with llama-server, vLLM, text-generation-inference, and any
OpenAI-compatible API (including OpenAI itself).

This enables tool calling with GPT-OSS-120B via llama.cpp server.
"""

# DEPRECATED - See llmc.backends.LiteLLMAgentBackend


from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any

import httpx

from llmc_agent.backends.base import Backend, GenerateRequest, GenerateResponse


class OpenAICompatBackend(Backend):
    """OpenAI-compatible LLM backend.
    
    Works with:
    - llama.cpp server (http://host:8080/v1/...)
    - vLLM
    - text-generation-inference
    - OpenAI API
    - Any OpenAI-compatible endpoint
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        api_key: str | None = None,
        timeout: int = 300,
        temperature: float = 0.7,
        model: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.default_model = model
        
        # Build headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a response (non-streaming)."""

        # Build messages - prepend system as first message
        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload = {
            "model": request.model or self.default_model or "default",
            "messages": messages,
            "stream": False,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

        # Parse OpenAI response format
        choice = data["choices"][0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return GenerateResponse(
            content=message.get("content", ""),
            tokens_prompt=usage.get("prompt_tokens", 0),
            tokens_completion=usage.get("completion_tokens", 0),
            model=data.get("model", request.model),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def generate_stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        """Generate a response with streaming."""

        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload = {
            "model": request.model or self.default_model or "default",
            "messages": messages,
            "stream": True,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
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
            tools: List of tools in OpenAI format

        Returns:
            GenerateResponse with tool_calls populated if model used tools
        """

        # Build messages
        messages = [
            {"role": "system", "content": request.system},
            *request.messages,
        ]

        payload: dict[str, Any] = {
            "model": request.model or self.default_model or "default",
            "messages": messages,
            "stream": False,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

        # Parse OpenAI response format
        choice = data["choices"][0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        # Extract tool calls if present (OpenAI format)
        tool_calls_raw = message.get("tool_calls", [])
        tool_calls = []
        for tc in tool_calls_raw:
            # Normalize to our format
            tool_calls.append({
                "function": {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                },
                "id": tc.get("id", ""),
                "type": "function",
            })

        return GenerateResponse(
            content=message.get("content") or "",
            tokens_prompt=usage.get("prompt_tokens", 0),
            tokens_completion=usage.get("completion_tokens", 0),
            model=data.get("model", request.model),
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=tool_calls,
            raw_response=data,
        )

    async def health_check(self) -> bool:
        """Check if backend is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # Try /models endpoint (OpenAI standard)
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                )
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                # Handle both OpenAI format and llama.cpp format
                if "models" in data:
                    return [m.get("name", m.get("id", "")) for m in data["models"]]
                elif "data" in data:
                    return [m.get("id", "") for m in data["data"]]
                return []
        except Exception:
            return []
