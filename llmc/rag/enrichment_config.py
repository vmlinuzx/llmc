"""Provider registry and configuration for remote LLM backends.

This module defines the provider registry with defaults for major LLM API providers
and handles loading provider configurations from llmc.toml.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from llmc.rag.enrichment_reliability import PricingInfo, RateLimitConfig

# =============================================================================
# Provider Metadata
# =============================================================================


@dataclass
class ProviderMetadata:
    """Metadata for a remote LLM provider."""

    adapter_type: str  # Which adapter class to use
    auth_env_var: str | None  # Environment variable for API key
    base_url: str | None  # Base URL for API (None = use from config)
    rate_limit: RateLimitConfig  # Default rate limits
    pricing: PricingInfo | None  # Default pricing (None = unknown/free)


# Provider registry with sensible defaults
# Users can override in llmc.toml
PROVIDERS: dict[str, ProviderMetadata] = {
    "ollama": ProviderMetadata(
        adapter_type="ollama",
        auth_env_var=None,
        base_url=None,  # Must be specified in config
        rate_limit=RateLimitConfig(
            requests_per_minute=1000,  # Local, no hard limit
            tokens_per_minute=10_000_000,  # Local, no hard limit
        ),
        pricing=None,  # Free (local)
    ),
    "gemini": ProviderMetadata(
        adapter_type="google-genai",
        auth_env_var="GOOGLE_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        rate_limit=RateLimitConfig(
            requests_per_minute=60,
            tokens_per_minute=1_000_000,
        ),
        pricing=PricingInfo(
            input_per_million=0.075,  # Gemini 1.5 Flash
            output_per_million=0.30,
        ),
    ),
    "openai": ProviderMetadata(
        adapter_type="openai",
        auth_env_var="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        rate_limit=RateLimitConfig(
            requests_per_minute=500,  # Tier 1 default
            tokens_per_minute=90_000,
        ),
        pricing=PricingInfo(
            input_per_million=0.15,  # GPT-4o-mini approx
            output_per_million=0.60,
        ),
    ),
    "anthropic": ProviderMetadata(
        adapter_type="anthropic",
        auth_env_var="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        rate_limit=RateLimitConfig(
            requests_per_minute=50,  # Tier 1 default
            tokens_per_minute=100_000,
        ),
        pricing=PricingInfo(
            input_per_million=0.25,  # Claude 3 Haiku
            output_per_million=1.25,
        ),
    ),
    "groq": ProviderMetadata(
        adapter_type="openai",  # OpenAI-compatible
        auth_env_var="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        rate_limit=RateLimitConfig(
            requests_per_minute=30,  # Free tier
            tokens_per_minute=6_000,
        ),
        pricing=PricingInfo(
            input_per_million=0.05,  # Llama 3 70B approx
            output_per_million=0.08,
        ),
    ),
    "minimax": ProviderMetadata(
        adapter_type="anthropic",  # Minimax uses Anthropic-compatible API
        auth_env_var="MINIMAX_API_KEY",
        base_url="https://api.minimax.io/anthropic",
        rate_limit=RateLimitConfig(
            requests_per_minute=60,
            tokens_per_minute=100_000,
        ),
        pricing=PricingInfo(
            input_per_million=0.10,  # Approximate pricing
            output_per_million=0.20,
        ),
    ),
    "azure": ProviderMetadata(
        adapter_type="azure-openai",
        auth_env_var="AZURE_OPENAI_API_KEY",
        base_url=None,  # Deployment-specific, must be in config
        rate_limit=RateLimitConfig(
            requests_per_minute=60,
            tokens_per_minute=90_000,
        ),
        pricing=None,  # Varies by deployment
    ),
}


# =============================================================================
# Configuration Loading
# =============================================================================


@dataclass
class EnrichmentProviderConfig:
    """Configuration for a specific provider instance."""

    name: str  # Backend name (e.g., "gemini-flash")
    provider: str  # Provider type (e.g., "gemini")
    model: str  # Model name
    url: str | None  # Base URL override
    api_key: str | None  # API key (from env or config)
    timeout_seconds: int
    enabled: bool
    retry_max: int
    retry_backoff_base: float
    rate_limit_override: RateLimitConfig | None
    pricing_override: PricingInfo | None


def get_provider_metadata(provider: str) -> ProviderMetadata | None:
    """Get provider metadata from registry.

    Args:
        provider: _ALLOWED_PROVIDERS = {"ollama", "gateway", "gemini", "minimax", "openai", "anthropic", "groq", "azure"})

    Returns:
        ProviderMetadata or None if not found
    """
    return PROVIDERS.get(provider)


def resolve_api_key(provider: str, config: dict[str, Any]) -> str | None:
    """Resolve API key from config or environment.

    Priority:
    1. Explicit api_key in config
    2. Environment variable specified in config
    3. Default environment variable from registry

    Args:
        provider: Provider name
        config: Config dict for this backend

    Returns:
        API key or None
    """
    # Check explicit key in config
    if "api_key" in config:
        val = config["api_key"]
        return str(val) if val is not None else None

    # Check custom env var in config
    if "api_key_env" in config:
        env_var = config["api_key_env"]
        return os.getenv(env_var)

    # Check default env var from registry
    metadata = get_provider_metadata(provider)
    if metadata and metadata.auth_env_var:
        return os.getenv(metadata.auth_env_var)

    return None


def load_provider_config(
    backend_config: dict[str, Any], provider_defaults: dict[str, Any] | None = None
) -> EnrichmentProviderConfig:
    """Load and validate provider configuration.

    Args:
        backend_config: Backend config from llmc.toml [[enrichment.chain]]
        provider_defaults: Optional provider-level defaults from [enrichment.providers.{name}]

    Returns:
        EnrichmentProviderConfig instance
    """
    provider = backend_config.get("provider", "")
    metadata = get_provider_metadata(provider)

    # Resolve API key
    api_key = resolve_api_key(provider, backend_config)
    if provider_defaults:
        api_key = api_key or resolve_api_key(provider, provider_defaults)

    # Resolve base URL
    url = backend_config.get("url")
    if not url and metadata:
        url = metadata.base_url

    # Rate limit overrides
    rate_limit_override = None
    rpm = backend_config.get("rpm_limit") or (
        provider_defaults.get("rpm_limit") if provider_defaults else None
    )
    tpm = backend_config.get("tpm_limit") or (
        provider_defaults.get("tpm_limit") if provider_defaults else None
    )
    if rpm or tpm:
        rate_limit_override = RateLimitConfig(
            requests_per_minute=rpm or (metadata.rate_limit.requests_per_minute if metadata else 60),
            tokens_per_minute=tpm or (metadata.rate_limit.tokens_per_minute if metadata else 1_000_000),
        )

    # Pricing overrides
    pricing_override = None
    input_price = backend_config.get("input_price_per_million")
    output_price = backend_config.get("output_price_per_million")
    if input_price is not None or output_price is not None:
        pricing_override = PricingInfo(
            input_per_million=input_price or 0.0,
            output_per_million=output_price or 0.0,
        )

    return EnrichmentProviderConfig(
        name=backend_config.get("name", f"{provider}-backend"),
        provider=provider,
        model=backend_config.get("model", ""),
        url=url,
        api_key=api_key,
        timeout_seconds=backend_config.get("timeout_seconds", 30),
        enabled=backend_config.get("enabled", True),
        retry_max=backend_config.get("retry_max", 3),
        retry_backoff_base=backend_config.get("retry_backoff_base", 1.0),
        rate_limit_override=rate_limit_override,
        pricing_override=pricing_override,
    )


def build_pricing_map(
    enrichment_config: dict[str, Any]
) -> dict[str, PricingInfo]:
    """Build pricing map from llmc.toml enrichment config.

    Args:
        enrichment_config: The [enrichment] section from llmc.toml

    Returns:
        Dict mapping provider name to PricingInfo
    """
    pricing_map: dict[str, PricingInfo] = {}

    # Load from [enrichment.pricing.*] sections
    pricing_section = enrichment_config.get("pricing", {})
    for provider, pricing_data in pricing_section.items():
        if isinstance(pricing_data, dict):
            pricing_map[provider] = PricingInfo(
                input_per_million=pricing_data.get("input", 0.0),
                output_per_million=pricing_data.get("output", 0.0),
            )

    # Fill in defaults from registry for missing providers
    for provider, metadata in PROVIDERS.items():
        if provider not in pricing_map and metadata.pricing:
            pricing_map[provider] = metadata.pricing

    return pricing_map


__all__ = [
    "ProviderMetadata",
    "PROVIDERS",
    "EnrichmentProviderConfig",
    "get_provider_metadata",
    "resolve_api_key",
    "load_provider_config",
    "build_pricing_map",
]
