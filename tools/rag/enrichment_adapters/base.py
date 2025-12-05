"""Base remote backend adapter for enrichment.

This module provides the base class for remote LLM API providers with:
- HTTP client management
- Authentication handling
- Retry middleware integration
- Rate limiting
- Circuit breaker
- Cost tracking
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any

from tools.rag.enrichment_backends import BackendError
from tools.rag.enrichment_config import (
    EnrichmentProviderConfig,
)
from tools.rag.enrichment_reliability import (
    CircuitBreaker,
    CostTracker,
    RateLimiter,
    RetryConfig,
    RetryMiddleware,
)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)


class RemoteBackend(ABC):
    """Base class for remote LLM API backends.

    Provides common functionality for all remote providers:
    - HTTP client management
    - Authentication
    - Retry logic
    - Rate limiting
    - Circuit breaker
    - Response parsing

    Subclasses must implement:
    - _build_request_payload()
    - _parse_response()
    - _extract_token_counts()
    """

    def __init__(
        self,
        config: EnrichmentProviderConfig,
        *,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        cost_tracker: CostTracker | None = None,
    ):
        """Initialize remote backend.

        Args:
            config: Provider configuration
            rate_limiter: Optional rate limiter instance
            circuit_breaker: Optional circuit breaker instance
            cost_tracker: Optional cost tracker instance
        """
        if httpx is None:
            raise ImportError(
                "httpx is required for remote backends. "
                "Install with: pip install httpx"
            )

        self._config = config
        self._rate_limiter = rate_limiter
        self._circuit_breaker = circuit_breaker
        self._cost_tracker = cost_tracker

        # Build HTTP client
        self._client = self._build_client()

        # Build retry middleware
        self._retry_middleware = RetryMiddleware(
            RetryConfig(
                max_retries=config.retry_max,
                base_delay=config.retry_backoff_base,
                max_delay=60.0,
                jitter_pct=0.1,
            )
        )

    def _build_client(self) -> Any:
        """Build HTTP client with auth and timeout."""
        headers = self._build_headers()
        base_url = self._config.url

        timeout = httpx.Timeout(
            self._config.timeout_seconds,
            connect=10.0,
        )

        return httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including authentication.

        Subclasses can override for provider-specific headers.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }

        # Add API key if present
        if self._config.api_key:
            # Most providers use Bearer token
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        return headers

    @property
    def config(self) -> EnrichmentProviderConfig:
        """Return backend configuration."""
        return self._config

    def describe_host(self) -> str | None:
        """Return human-readable host description."""
        return self._config.url

    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate enrichment via remote API.

        Args:
            prompt: Enrichment prompt to send to LLM
            item: Span data dictionary (for context/debugging)

        Returns:
            Tuple of (result_dict, metadata_dict)

        Raises:
            BackendError: On any failure
        """
        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.can_proceed():
            raise BackendError(
                f"Circuit breaker is open for {self._config.provider}",
                failure_type="circuit_breaker_open",
            )

        # Check budget
        if self._cost_tracker:
            # Estimate tokens (rough: ~1 token per 4 chars)
            estimated_tokens = len(prompt) // 4
            if not self._cost_tracker.check_budget(
                self._config.provider, estimated_tokens
            ):
                raise BackendError(
                    f"Budget exceeded for {self._config.provider}",
                    failure_type="budget_exceeded",
                )

        # Rate limiting
        if self._rate_limiter:
            estimated_tokens = len(prompt) // 4
            self._rate_limiter.wait_if_needed(estimated_tokens)

        # Execute with retry
        def _execute():
            return self._execute_request(prompt, item)

        try:
            result, meta = self._retry_middleware.execute(
                _execute,
                is_retryable=self._is_retryable_error,
            )

            # Record success
            if self._circuit_breaker:
                self._circuit_breaker.record_success()

            # Record cost
            if self._cost_tracker:
                input_tokens = meta.get("prompt_tokens", 0)
                output_tokens = meta.get("completion_tokens", 0)
                cost_info = self._cost_tracker.record(
                    self._config.provider, input_tokens, output_tokens
                )
                meta["cost"] = cost_info

            # Record rate limit usage
            if self._rate_limiter:
                total_tokens = meta.get("total_tokens", 0)
                if total_tokens > 0:
                    self._rate_limiter.record(total_tokens)

            return result, meta

        except Exception as exc:
            # Record failure
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()

            # Re-raise as BackendError if not already
            if isinstance(exc, BackendError):
                raise
            raise BackendError(
                f"{self._config.provider} error: {exc}",
                failure_type="backend_error",
            ) from exc

    def _execute_request(
        self, prompt: str, item: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute the actual HTTP request.

        Args:
            prompt: Enrichment prompt
            item: Span data

        Returns:
            Tuple of (result, metadata)

        Raises:
            BackendError: On failure
        """
        # Build request
        endpoint, payload = self._build_request_payload(prompt, item)

        logger.debug(
            f"Requesting {self._config.provider} {self._config.model}: "
            f"{len(prompt)} chars"
        )

        try:
            response = self._client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        except httpx.TimeoutException as e:
            raise BackendError(
                f"{self._config.provider} timeout after {self._config.timeout_seconds}s",
                failure_type="timeout",
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            # Map status codes to failure types
            if status_code == 429:
                failure_type = "rate_limit"
            elif status_code == 401:
                failure_type = "auth_error"
            elif status_code == 403:
                failure_type = "forbidden"
            elif status_code == 404:
                failure_type = "not_found"
            elif 400 <= status_code < 500:
                failure_type = "client_error"
            else:
                failure_type = "server_error"

            raise BackendError(
                f"{self._config.provider} HTTP {status_code}: {e.response.text[:200]}",
                failure_type=failure_type,
            ) from e

        except Exception as e:
            raise BackendError(
                f"{self._config.provider} error: {e}",
                failure_type="backend_error",
            ) from e

        # Parse response
        result = self._parse_response(data, item)

        # Extract metadata
        input_tokens, output_tokens = self._extract_token_counts(data)
        meta = {
            "model": self._config.model,
            "provider": self._config.provider,
            "host": self._config.url,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

        return result, meta

    @abstractmethod
    def _build_request_payload(
        self, prompt: str, item: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Build provider-specific request payload.

        Args:
            prompt: Enrichment prompt
            item: Span data

        Returns:
            Tuple of (endpoint_path, request_payload)
        """
        pass

    @abstractmethod
    def _parse_response(self, data: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        """Parse provider-specific response into enrichment format.

        Args:
            data: Raw API response JSON
            item: Original span data

        Returns:
            Enrichment dict with summary, key_topics, etc.
        """
        pass

    @abstractmethod
    def _extract_token_counts(self, data: dict[str, Any]) -> tuple[int, int]:
        """Extract token counts from response.

        Args:
            data: Raw API response JSON

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        pass

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Determine if error is retryable.

        Args:
            exc: Exception that occurred

        Returns:
            True if should retry
        """
        if not isinstance(exc, BackendError):
            return False

        retryable_types = {
            "timeout",
            "rate_limit",
            "server_error",
        }

        return exc.failure_type in retryable_types

    def _parse_enrichment_json(self, text: str, item: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM output into enrichment fields.

        Shared utility for parsing JSON from LLM responses.

        Args:
            text: Raw LLM response text
            item: Original span data (for fallback)

        Returns:
            Dict with summary, key_topics, complexity, etc.
        """
        # Try to find JSON block in response (handles markdown fences)
        # Look for {...} or ```json\n{...}\n```

        # First try: look for code fence with json
        fence_match = re.search(
            r'```(?:json)?\s*\n(\{.*?\})\s*\n```',
            text,
            re.DOTALL
        )
        if fence_match:
            try:
                return dict(json.loads(fence_match.group(1)))
            except json.JSONDecodeError:
                pass

        # Second try: find bare JSON object
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return dict(json.loads(json_match.group()))
            except json.JSONDecodeError:
                pass

        # Fallback: return raw text as summary
        summary = text.strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return {
            "summary": summary,
            "key_topics": [],
            "complexity": "unknown",
            "evidence": "",
        }

    def close(self) -> None:
        """Close HTTP client connection."""
        if self._client:
            self._client.close()

    def __enter__(self) -> RemoteBackend:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


__all__ = ["RemoteBackend"]
