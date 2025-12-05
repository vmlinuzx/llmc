"""Backend factory for creating enrichment adapters.

This module provides factory functions to instantiate the correct backend adapter
based on provider configuration, with support for remote providers including:
- Ollama (local)
- Gemini
- OpenAI
- Anthropic
- Groq
"""

from __future__ import annotations

import logging
from typing import Any

from tools.rag.config_enrichment import EnrichmentBackendSpec
from tools.rag.enrichment_adapters import (
    AnthropicBackend,
    GeminiBackend,
    OllamaBackend,
    OpenAICompatBackend,
)
from tools.rag.enrichment_backends import BackendAdapter
from tools.rag.enrichment_config import (
    get_provider_metadata,
    load_provider_config,
)
from tools.rag.enrichment_reliability import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CostTracker,
    CostTrackerConfig,
    RateLimiter,
)

logger = logging.getLogger(__name__)


def create_backend_from_spec(
    spec: EnrichmentBackendSpec,
    *,
    cost_tracker: CostTracker | None = None,
    provider_defaults: dict[str, Any] | None = None,
) -> BackendAdapter:
    """Factory function to create backend adapter from spec.

    This replaces the direct OllamaBackend.from_spec() calls and supports
    all providers (Ollama, Gemini, OpenAI, Anthropic, Groq).

    Args:
        spec: Backend specification from llmc.toml
        cost_tracker: Optional shared cost tracker instance
        provider_defaults: Optional provider-level defaults

    Returns:
        Configured backend adapter

    Raises:
        ValueError: If provider is unknown or configuration is invalid
    """
    provider = spec.provider.lower() if spec.provider else "ollama"

    # Special case: Ollama uses the legacy spec-based factory
    if provider == "ollama":
        return OllamaBackend.from_spec(spec)

    # Convert spec to EnrichmentProviderConfig
    spec_dict = {
        "name": spec.name,
        "provider": spec.provider,
        "model": spec.model or "",
        "url": spec.url,
        "timeout_seconds": spec.timeout_seconds or 30,
        "enabled": spec.enabled,
        "retry_max": getattr(spec, "retry_max", 3),
        "retry_backoff_base": getattr(spec, "retry_backoff_base", 1.0),
    }

    config = load_provider_config(spec_dict, provider_defaults)

    # Get provider metadata for defaults
    metadata = get_provider_metadata(provider)
    if not metadata:
        raise ValueError(f"Unknown provider: {provider}")

    # Create rate limiter
    rate_limit_config = config.rate_limit_override or (
        metadata.rate_limit if metadata else None
    )
    rate_limiter = RateLimiter(rate_limit_config) if rate_limit_config else None

    # Create circuit breaker
    circuit_breaker = CircuitBreaker(
        CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )
    )

    # Select adapter class based on provider
    adapter_type = metadata.adapter_type

    if adapter_type == "google-genai":
        return GeminiBackend(
            config,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            cost_tracker=cost_tracker,
        )

    elif adapter_type == "openai":
        # Works for OpenAI and Groq (OpenAI-compatible)
        return OpenAICompatBackend(
            config,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            cost_tracker=cost_tracker,
        )

    elif adapter_type == "anthropic":
        return AnthropicBackend(
            config,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            cost_tracker=cost_tracker,
        )

    else:
        raise ValueError(
            f"Unsupported adapter type '{adapter_type}' for provider '{provider}'"
        )


def create_cost_tracker_from_config(
    enrichment_config: dict[str, Any]
) -> CostTracker | None:
    """Create cost tracker from enrichment configuration.

    Args:
        enrichment_config: The [enrichment] section from llmc.toml

    Returns:
        CostTracker instance or None if no cost tracking configured
    """
    from tools.rag.enrichment_config import build_pricing_map

    # Check if cost caps are configured
    daily_cap = enrichment_config.get("daily_cost_cap_usd")
    monthly_cap = enrichment_config.get("monthly_cost_cap_usd")

    if daily_cap is None and monthly_cap is None:
        # No cost tracking needed
        return None

    # Build pricing map
    pricing_map = build_pricing_map(enrichment_config)

    config = CostTrackerConfig(
        pricing=pricing_map,
        daily_cap_usd=daily_cap,
        monthly_cap_usd=monthly_cap,
    )

    logger.info(
        f"Cost tracking enabled: daily=${daily_cap}, monthly=${monthly_cap}"
    )

    return CostTracker(config)


__all__ = [
    "create_backend_from_spec",
    "create_cost_tracker_from_config",
]
