"""Shared logic for LiteLLM backends.

This module contains common functionality used by both:
- LiteLLMAgentBackend (async, for llmc_agent)
- LiteLLMEnrichmentAdapter (sync, for RAG enrichment)

Design: HLD-litellm-migration-FINAL.md Section 4.2
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from litellm.types.utils import Message

# Lazy import litellm to avoid import-time cost
_litellm_imported = False


def _ensure_litellm() -> None:
    """Lazy import litellm and configure it."""
    global _litellm_imported
    if not _litellm_imported:
        import litellm
        litellm.drop_params = True  # Drop unsupported params instead of erroring
        _litellm_imported = True


@dataclass
class LiteLLMConfig:
    """Configuration for LiteLLM backends.
    
    Attributes:
        model: LiteLLM format model string (e.g., "ollama_chat/qwen3-next-80b")
        api_key: API key for the provider (None for local providers like Ollama)
        api_base: Custom API base URL (e.g., for llama.cpp server)
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        num_retries: Number of retries for transient errors
        drop_params: Drop unsupported parameters instead of erroring
    """

    model: str  # LiteLLM format: "provider/model"
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: float = 120.0
    num_retries: int = 3
    drop_params: bool = True


def to_litellm_model(provider: str, model: str) -> str:
    """Convert provider+model to LiteLLM format.
    
    Args:
        provider: Provider name (e.g., "ollama", "openai", "anthropic")
        model: Model name (e.g., "qwen3-next-80b", "gpt-4o")
    
    Returns:
        LiteLLM format string (e.g., "ollama_chat/qwen3-next-80b")
    
    Examples:
        >>> to_litellm_model("ollama", "qwen3-next-80b")
        'ollama_chat/qwen3-next-80b'
        >>> to_litellm_model("openai", "gpt-4o")
        'openai/gpt-4o'
        >>> to_litellm_model("groq", "llama3-70b-8192")
        'groq/llama3-70b-8192'
    """
    if provider == "ollama":
        return f"ollama_chat/{model}"  # Use chat endpoint for multi-turn
    elif provider == "groq":
        return f"groq/{model}"  # Native Groq routing
    return f"{provider}/{model}"


class LiteLLMCore:
    """Shared implementation logic for LiteLLM backends.
    
    This class is used by composition (not inheritance) by both
    LiteLLMAgentBackend and LiteLLMEnrichmentAdapter.
    """

    def __init__(self, config: LiteLLMConfig) -> None:
        self.config = config
        _ensure_litellm()

    def get_common_kwargs(self) -> dict[str, Any]:
        """Get common kwargs for litellm calls.
        
        Returns:
            Dict of kwargs to pass to litellm.completion/acompletion
        """
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "num_retries": self.config.num_retries,
        }
        
        # Only include if set (None values can cause issues)
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
            
        return kwargs

    def map_exception(self, exc: Exception) -> Exception:
        """Map LiteLLM exceptions to BackendError.
        
        Args:
            exc: Original exception from LiteLLM
            
        Returns:
            BackendError with appropriate failure_type
        """
        # Import here to avoid circular imports
        from llmc.rag.enrichment_backends import BackendError
        
        # Import litellm exceptions
        from litellm.exceptions import (
            APIError,
            AuthenticationError,
            RateLimitError,
            ServiceUnavailableError,
            Timeout,
        )

        if isinstance(exc, RateLimitError):
            return BackendError(str(exc), failure_type="rate_limit")
        elif isinstance(exc, Timeout):
            return BackendError(str(exc), failure_type="timeout")
        elif isinstance(exc, AuthenticationError):
            return BackendError(str(exc), failure_type="auth_error")
        elif isinstance(exc, ServiceUnavailableError):
            return BackendError(str(exc), failure_type="server_error")
        elif isinstance(exc, APIError):
            return BackendError(str(exc), failure_type="api_error")
        return BackendError(str(exc), failure_type="backend_error")

    def parse_tool_calls(self, message: Message) -> list[dict[str, Any]]:
        """Extract and normalize tool calls from response.
        
        Args:
            message: LiteLLM message object from response
            
        Returns:
            List of normalized tool call dicts in OpenAI format
        """
        tool_calls: list[dict[str, Any]] = []
        
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                    "id": tc.id,
                    "type": "function",
                })
        return tool_calls

    def parse_enrichment_json(self, text: str) -> dict[str, Any]:
        """Parse LLM output into enrichment fields.
        
        Handles various JSON formats:
        - Code-fenced JSON (```json ... ```)
        - Bare JSON objects
        - Fallback to extracting text as summary
        
        Args:
            text: Raw LLM output text
            
        Returns:
            Dict with enrichment fields (summary, key_topics, complexity, evidence)
        """
        # Try code fence first (most common)
        fence_match = re.search(
            r"```(?:json)?\s*\n(\{.*?\})\s*\n```",
            text,
            re.DOTALL,
        )
        if fence_match:
            try:
                return dict(json.loads(fence_match.group(1)))
            except json.JSONDecodeError:
                pass

        # Try bare JSON object
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                return dict(json.loads(json_match.group()))
            except json.JSONDecodeError:
                pass

        # Fallback: use text as summary
        return {
            "summary": text.strip()[:500],
            "key_topics": [],
            "complexity": "unknown",
            "evidence": "",
        }

    def should_skip_tool_choice(self) -> bool:
        """Check if tool_choice should be skipped for this model.
        
        Some models (notably Ollama) can hang or behave unexpectedly
        when tool_choice is specified.
        
        Returns:
            True if tool_choice should be omitted
        """
        # Ollama can hang with tool_choice
        return self.config.model.startswith("ollama")

    def describe_host(self) -> str | None:
        """Return human-readable host description.
        
        Returns:
            API base URL if custom, otherwise provider name
        """
        if self.config.api_base:
            return self.config.api_base
        provider = (
            self.config.model.split("/")[0]
            if "/" in self.config.model
            else "unknown"
        )
        return f"{provider} API"


__all__ = [
    "LiteLLMConfig",
    "LiteLLMCore",
    "to_litellm_model",
]
