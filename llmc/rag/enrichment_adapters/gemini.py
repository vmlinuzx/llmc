"""Gemini backend adapter for enrichment.

This adapter integrates with Google's Gemini API for enrichment generation.
"""

from __future__ import annotations

import logging
from typing import Any

from llmc.rag.enrichment_adapters.base import RemoteBackend

logger = logging.getLogger(__name__)


class GeminiBackend(RemoteBackend):
    """BackendAdapter implementation for Google Gemini.

    Communicates with Gemini's REST API to generate enrichment summaries.

    Usage:
        config = EnrichmentProviderConfig(
            name="gemini-flash",
            provider="gemini",
            model="gemini-1.5-flash",
            url="https://generativelanguage.googleapis.com/v1beta",
            api_key="...",
            timeout_seconds=30,
            enabled=True,
            retry_max=3,
            retry_backoff_base=1.0,
            rate_limit_override=None,
            pricing_override=None,
        )
        backend = GeminiBackend(config)
        result, meta = backend.generate(prompt, item=span_data)
    """

    def _build_headers(self) -> dict[str, str]:
        """Build Gemini-specific headers.

        Gemini uses API key as a query parameter or x-goog-api-key header,
        not Bearer token.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }

        if self._config.api_key:
            headers["x-goog-api-key"] = self._config.api_key

        return headers

    def _build_request_payload(
        self, prompt: str, item: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Build Gemini API request payload.

        Args:
            prompt: Enrichment prompt
            item: Span data (for context)

        Returns:
            Tuple of (endpoint, payload)
        """
        # Gemini endpoint format: /models/{model}:generateContent
        endpoint = f"/models/{self._config.model}:generateContent"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            },
        }

        return endpoint, payload

    def _parse_response(self, data: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        """Parse Gemini response into enrichment format.

        Gemini response structure:
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "..."}],
                        "role": "model"
                    },
                    "finishReason": "STOP",
                    ...
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 123,
                "candidatesTokenCount": 456,
                "totalTokenCount": 579
            }
        }

        Args:
            data: Raw Gemini API response
            item: Original span data

        Returns:
            Enrichment dict
        """
        # Extract text from response
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("Gemini response has no candidates")
                return self._fallback_enrichment(item)

            first_candidate = candidates[0]
            content = first_candidate.get("content", {})
            parts = content.get("parts", [])

            if not parts:
                logger.warning("Gemini response has no parts")
                return self._fallback_enrichment(item)

            text = parts[0].get("text", "")

            if not text:
                logger.warning("Gemini response text is empty")
                return self._fallback_enrichment(item)

            # Parse the text as enrichment JSON
            return self._parse_enrichment_json(text, item)

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return self._fallback_enrichment(item)

    def _extract_token_counts(self, data: dict[str, Any]) -> tuple[int, int]:
        """Extract token counts from Gemini response.

        Args:
            data: Raw Gemini API response

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

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


__all__ = ["GeminiBackend"]
