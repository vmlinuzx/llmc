"""OpenAI-compatible backend adapter for enrichment.

This adapter works with:
- OpenAI API
- Groq API (OpenAI-compatible)
- Any other OpenAI-compatible endpoints
"""

from __future__ import annotations

import logging
from typing import Any

from llmc.rag.enrichment_adapters.base import RemoteBackend

logger = logging.getLogger(__name__)


class OpenAICompatBackend(RemoteBackend):
    """BackendAdapter for OpenAI-compatible APIs.

    Supports:
    - OpenAI (GPT-4, GPT-3.5, etc.)
    - Groq (Llama, Mixtral, etc.)
    - Any OpenAI-compatible endpoint

    Usage:
        # OpenAI
        config = EnrichmentProviderConfig(
            name="gpt-4o-mini",
            provider="openai",
            model="gpt-4o-mini",
            url="https://api.openai.com/v1",
            api_key="sk-...",
            timeout_seconds=30,
            enabled=True,
            retry_max=3,
            retry_backoff_base=1.0,
            rate_limit_override=None,
            pricing_override=None,
        )

        # Groq
        config = EnrichmentProviderConfig(
            name="groq-llama",
            provider="groq",
            model="llama3-70b-8192",
            url="https://api.groq.com/openai/v1",
            api_key="gsk_...",
            ...
        )

        backend = OpenAICompatBackend(config)
        result, meta = backend.generate(prompt, item=span_data)
    """

    def _build_request_payload(
        self, prompt: str, item: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Build OpenAI-compatible API request payload.

        Args:
            prompt: Enrichment prompt
            item: Span data (for context)

        Returns:
            Tuple of (endpoint, payload)
        """
        endpoint = "/chat/completions"

        payload = {
            "model": self._config.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        return endpoint, payload

    def _parse_response(
        self, data: dict[str, Any], item: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse OpenAI-compatible response into enrichment format.

        OpenAI response structure:
        {
            "id": "chatcmpl-...",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "..."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "total_tokens": 579
            }
        }

        Args:
            data: Raw API response
            item: Original span data

        Returns:
            Enrichment dict
        """
        try:
            choices = data.get("choices", [])
            if not choices:
                logger.warning(f"{self._config.provider} response has no choices")
                return self._fallback_enrichment(item)

            first_choice = choices[0]
            message = first_choice.get("message", {})
            content = message.get("content", "")

            if not content:
                logger.warning(f"{self._config.provider} response content is empty")
                return self._fallback_enrichment(item)

            # Parse the content as enrichment JSON
            return self._parse_enrichment_json(content, item)

        except Exception as e:
            logger.error(f"Error parsing {self._config.provider} response: {e}")
            return self._fallback_enrichment(item)

    def _extract_token_counts(self, data: dict[str, Any]) -> tuple[int, int]:
        """Extract token counts from OpenAI-compatible response.

        Args:
            data: Raw API response

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return input_tokens, output_tokens

    def _fallback_enrichment(self, item: dict[str, Any]) -> dict[str, Any]:
        """Create fallback enrichment when parsing fails.

        Args:
            item: Original span data

        Returns:
            Basic enrichment dict
        """
        return {
            "summary": "Enrichment generation failed",
            "key_topics": [],
            "complexity": "unknown",
            "evidence": "",
        }


__all__ = ["OpenAICompatBackend"]
