"""LiteLLM adapter for enrichment pipeline (sync interface).

This adapter implements the BackendAdapter Protocol for sync enrichment use cases.
It integrates with the existing reliability middleware (circuit breaker, rate limiter, cost tracker).

Design: HLD-litellm-migration-FINAL.md Section 4.4
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llmc.backends.litellm_core import LiteLLMConfig, LiteLLMCore
from llmc.rag.enrichment_backends import BackendError

if TYPE_CHECKING:
    from llmc.rag.enrichment_reliability import (
        CircuitBreaker,
        CostTracker,
        RateLimiter,
    )


class LiteLLMEnrichmentAdapter:
    """LiteLLM-based adapter for enrichment pipeline.

    Implements the BackendAdapter Protocol for sync enrichment use cases.
    Integrates with existing reliability middleware.
    
    Example:
        >>> config = LiteLLMConfig(model="ollama_chat/qwen3-next-80b")
        >>> adapter = LiteLLMEnrichmentAdapter(config)
        >>> result, meta = adapter.generate(prompt, item=span_dict)
    """

    def __init__(
        self,
        config: LiteLLMConfig,
        *,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        """Initialize the adapter.
        
        Args:
            config: LiteLLM configuration
            rate_limiter: Optional rate limiter for token/request throttling
            circuit_breaker: Optional circuit breaker for fail-fast behavior
            cost_tracker: Optional cost tracker with budget caps
        """
        self._core = LiteLLMCore(config)
        self._config = config
        self._rate_limiter = rate_limiter
        self._circuit_breaker = circuit_breaker
        self._cost_tracker = cost_tracker

    @property
    def config(self) -> LiteLLMConfig:
        """Return backend configuration (required by BackendAdapter Protocol)."""
        return self._config

    def describe_host(self) -> str | None:
        """Return human-readable host description."""
        return self._core.describe_host()

    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate enrichment via LiteLLM (synchronous).

        Implements BackendAdapter.generate() Protocol.
        
        Args:
            prompt: The enrichment prompt
            item: The span/item being enriched (for context)
            
        Returns:
            Tuple of (result_dict, metadata_dict)
            
        Raises:
            BackendError: If the call fails or budget/circuit breaker blocks
        """
        from litellm import completion

        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.can_proceed():
            raise BackendError(
                f"Circuit breaker open for {self._config.model}",
                failure_type="circuit_breaker_open",
            )

        # Check budget
        if self._cost_tracker:
            estimated_tokens = len(prompt) // 4
            provider = self._config.model.split("/")[0]
            if not self._cost_tracker.check_budget(provider, estimated_tokens):
                raise BackendError(
                    f"Budget exceeded for {provider}",
                    failure_type="budget_exceeded",
                )

        # Rate limiting (blocking wait)
        if self._rate_limiter:
            estimated_tokens = len(prompt) // 4
            self._rate_limiter.wait_if_needed(estimated_tokens)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = completion(
                messages=messages,
                **self._core.get_common_kwargs(),
            )

            if self._circuit_breaker:
                self._circuit_breaker.record_success()

        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            raise self._core.map_exception(e) from e

        # Parse response
        content = response.choices[0].message.content or ""
        result = self._core.parse_enrichment_json(content)

        # Extract usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Record cost
        cost_info: dict[str, Any] = {}
        if self._cost_tracker:
            provider = self._config.model.split("/")[0]
            cost_info = self._cost_tracker.record(provider, input_tokens, output_tokens)

        # Record rate limit usage
        if self._rate_limiter and usage:
            total_tokens = usage.total_tokens if hasattr(usage, "total_tokens") else (input_tokens + output_tokens)
            self._rate_limiter.record(total_tokens)

        meta = {
            "model": response.model,
            "provider": self._config.model.split("/")[0],
            "host": self.describe_host(),
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost_info,
        }

        return result, meta


__all__ = ["LiteLLMEnrichmentAdapter"]
