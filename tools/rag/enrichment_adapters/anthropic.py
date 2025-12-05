"""Anthropic (Claude) backend adapter for enrichment.

This adapter integrates with Anthropic's Claude API for enrichment generation.
"""

from __future__ import annotations

import logging
from typing import Any

from tools.rag.enrichment_adapters.base import RemoteBackend

logger = logging.getLogger(__name__)


class AnthropicBackend(RemoteBackend):
    """BackendAdapter implementation for Anthropic Claude.

    Communicates with Anthropic's Messages API to generate enrichment summaries.

    Usage:
        config = EnrichmentProviderConfig(
            name="claude-haiku",
            provider="anthropic",
            model="claude-3-haiku-20240307",
            url="https://api.anthropic.com/v1",
            api_key="sk-ant-...",
            timeout_seconds=30,
            enabled=True,
            retry_max=3,
            retry_backoff_base=1.0,
            rate_limit_override=None,
            pricing_override=None,
        )
        backend = AnthropicBackend(config)
        result, meta = backend.generate(prompt, item=span_data)
    """

    def _build_headers(self) -> dict[str, str]:
        """Build Anthropic-specific headers.

        Anthropic requires:
        - x-api-key header for authentication
        - anthropic-version header for API version
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",  # Latest stable version
        }

        if self._config.api_key:
            headers["x-api-key"] = self._config.api_key

        return headers

    def _build_request_payload(
        self, prompt: str, item: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Build Anthropic API request payload.

        Args:
            prompt: Enrichment prompt
            item: Span data (for context)

        Returns:
            Tuple of (endpoint, payload)
        """
        endpoint = "/messages"

        payload = {
            "model": self._config.model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.7,
        }

        return endpoint, payload

    def _parse_response(self, data: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        """Parse Anthropic response into enrichment format.

        Anthropic response structure:
        {
            "id": "msg_...",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "..."
                }
            ],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 123,
                "output_tokens": 456
            }
        }

        Args:
            data: Raw Anthropic API response
            item: Original span data

        Returns:
            Enrichment dict
        """
        try:
            content_blocks = data.get("content", [])
            if not content_blocks:
                logger.warning("Anthropic response has no content")
                return self._fallback_enrichment(item)

            # Extract text from content blocks
            # Minimax returns both "thinking" (reasoning) and "text" (answer) blocks
            # Prioritize "text" blocks, fall back to "thinking" only if no text found
            text = None
            thinking_fallback = None
            
            for block in content_blocks:
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "")
                    if text:  # Found a non-empty text block, use it
                        break
                elif block_type == "thinking" and thinking_fallback is None:
                    # Store first thinking block as fallback
                    thinking_fallback = block.get("thinking", "")
            
            # Use text if found, otherwise fall back to thinking
            if not text and thinking_fallback:
                text = thinking_fallback
                logger.debug("Using 'thinking' block as fallback (no 'text' block found)")

            if not text:
                logger.warning(f"No usable content in response blocks: {[b.get('type') for b in content_blocks]}")
                return self._fallback_enrichment(item)

            # Parse the text as enrichment JSON
            return self._parse_enrichment_json(text, item)

        except Exception as e:
            logger.error(f"Error parsing Anthropic response: {e}")
            return self._fallback_enrichment(item)

    def _extract_token_counts(self, data: dict[str, Any]) -> tuple[int, int]:
        """Extract token counts from Anthropic response.

        Args:
            data: Raw Anthropic API response

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

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


__all__ = ["AnthropicBackend"]
