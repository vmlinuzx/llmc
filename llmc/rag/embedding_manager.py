from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
from threading import Lock
from typing import Any

from .embedding_providers import (
    EmbeddingConfigError,
    EmbeddingMetadata,
    EmbeddingProvider,
    HashEmbeddingProvider,
    OllamaEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    ClinicalLongformerEmbeddingProvider,
)

logger = logging.getLogger(__name__)


PROVIDER_REGISTRY: dict[str, type[EmbeddingProvider]] = {
    "hash": HashEmbeddingProvider,
    "sentence-transformer": SentenceTransformerEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "clinical-longformer": ClinicalLongformerEmbeddingProvider,
}


@dataclass(frozen=True)
class EmbeddingProfileConfig:
    """Raw configuration for a single embedding profile.

    The `raw` mapping is typically derived from llmc.toml and contains at least:
    - provider: str
    - model: str
    - dimension: int
    - provider-specific nested config, e.g.:
      - sentence_transformer: { ... }
    """

    name: str
    raw: Mapping[str, Any]


def _build_metadata(
    provider_name: str,
    model: str,
    dimension: int,
    profile_name: str,
) -> EmbeddingMetadata:
    """Helper to construct EmbeddingMetadata with basic validation."""
    if dimension < 0:
        raise EmbeddingConfigError(f"Profile '{profile_name}' has negative dimension {dimension!r}")
    return EmbeddingMetadata(
        provider=provider_name,
        model=model,
        dimension=dimension,
        profile=profile_name,
    )


def create_provider_from_config(
    profile_name: str,
    cfg: Mapping[str, Any],
) -> EmbeddingProvider:
    """Construct a concrete EmbeddingProvider from a profile config.

    This function is profile-shape-aware but provider-agnostic in spirit:

    - `cfg` is usually one entry from [embeddings.profiles.<name>]
      or the legacy [embeddings] table.
    - Provider-specific nested config is expected under a key derived from the
      provider name by replacing '-' with '_', e.g.:
        - provider = "sentence-transformer"
          -> nested key "sentence_transformer"
    """
    try:
        provider_name = cfg["provider"]
    except KeyError as exc:  # pragma: no cover - config error path
        raise EmbeddingConfigError(f"Profile '{profile_name}' is missing 'provider'") from exc

    provider_cls = PROVIDER_REGISTRY.get(provider_name)
    if provider_cls is None:
        raise EmbeddingConfigError(
            f"Profile '{profile_name}' references unknown provider '{provider_name}'"
        )

    model = cfg.get("model", "")
    dimension = int(cfg.get("dimension", 0)) or 0

    # Provider-specific nested config, e.g. "sentence_transformer"
    provider_key = provider_name.replace("-", "_")
    provider_cfg = cfg.get(provider_key, {})

    metadata = _build_metadata(provider_name, model, dimension, profile_name)

    kwargs: dict[str, Any] = {}

    # hash provider: allow dimension override, default to 64 if unset.
    if provider_cls is HashEmbeddingProvider:
        if metadata.dimension <= 0:
            metadata = EmbeddingMetadata(
                provider=metadata.provider,
                model=metadata.model,
                dimension=64,
                profile=metadata.profile,
            )

    if provider_cls is SentenceTransformerEmbeddingProvider:
        kwargs["model_name"] = provider_cfg.get("model_name")
        kwargs["device"] = provider_cfg.get("device")
        kwargs["batch_size"] = int(provider_cfg.get("batch_size", 32))
        kwargs["normalize_embeddings"] = bool(provider_cfg.get("normalize_embeddings", True))
        kwargs["trust_remote_code"] = bool(provider_cfg.get("trust_remote_code", False))

    if provider_cls is OllamaEmbeddingProvider:
        kwargs["api_base"] = provider_cfg.get("api_base", "http://localhost:11434")
        kwargs["timeout"] = int(provider_cfg.get("timeout", 60))
    
    if provider_cls is ClinicalLongformerEmbeddingProvider:
        kwargs["config_path"] = provider_cfg.get("config_path")
        kwargs["max_seq_tokens"] = int(provider_cfg.get("max_seq_tokens", 4096))

    provider = provider_cls(metadata=metadata, **kwargs)
    logger.info(
        "Created embedding provider '%s' for profile '%s' (model=%s, dim=%d)",
        provider_name,
        profile_name,
        metadata.model,
        metadata.dimension,
    )
    return provider


class EmbeddingManager:
    """Central access point for embedding providers & profiles.

    Phase 4 responsibilities:

    - Support both legacy *single provider* configuration under [embeddings]
      and profile-based configuration under [embeddings.profiles.*].
    - Enforce that when profiles are present, embeddings.default_profile is set
      and references a valid profile.
    - Cache providers per profile and reuse them across calls.
    - Expose simple helper methods for introspection:

      - list_profiles()
      - get_default_profile()
      - get_profile_metadata(profile=None)
    """

    _instance: EmbeddingManager | None = None
    _lock: Lock = Lock()

    def __init__(
        self,
        profiles: dict[str, EmbeddingProfileConfig],
        default_profile: str,
    ) -> None:
        self._profiles = profiles
        self._default_profile = default_profile
        self._providers: dict[str, EmbeddingProvider] = {}
        self._providers_lock = Lock()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> EmbeddingManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._from_config()
        return cls._instance

    @classmethod
    def _from_config(cls) -> EmbeddingManager:
        """Build an EmbeddingManager from llmc configuration.

        This function expects a configuration loader named `get_llmc_config`
        to be available. To avoid hard-coding a single path, it tries a
        couple of reasonable locations and raises a clear error if they
        are missing so you can wire in your real config.

        Expected config shapes (TOML-ish):

        Legacy single-provider mode:

            [embeddings]
            provider  = "sentence-transformer"
            model     = "nomic-embed-text-v1.5"
            dimension = 768

            [embeddings.sentence_transformer]
            device = "cuda"
            batch_size = 32

        Profile-based mode:

            [embeddings]
            default_profile = "docs"

            [embeddings.profiles.docs]
            provider  = "sentence-transformer"
            model     = "nomic-embed-text-v1.5"
            dimension = 768

            [embeddings.profiles.docs.sentence_transformer]
            device = "cuda"
            batch_size = 32

            [embeddings.profiles.tags]
            provider  = "hash"
            dimension = 64
        """
        from llmc.config import get_llmc_config

        cfg = get_llmc_config()
        emb_cfg = cfg.get("embeddings", {})

        profiles_cfg = emb_cfg.get("profiles")
        profiles: dict[str, EmbeddingProfileConfig] = {}

        if profiles_cfg:
            default_profile = emb_cfg.get("default_profile")
            if not default_profile or default_profile not in profiles_cfg:
                raise EmbeddingConfigError(
                    "embeddings.default_profile must reference a defined profile "
                    "when embeddings.profiles.* is used"
                )
            for name, raw in profiles_cfg.items():
                if not isinstance(raw, Mapping):
                    raise EmbeddingConfigError(f"embeddings.profiles.{name} must be a table/object")
                profiles[name] = EmbeddingProfileConfig(name=name, raw=raw)
        else:
            # Legacy single-provider config: treat [embeddings] as a single profile.
            if "provider" not in emb_cfg:
                raise EmbeddingConfigError(
                    "No embeddings.profiles.* defined and no legacy embeddings.provider found"
                )
            profiles["default"] = EmbeddingProfileConfig(name="default", raw=emb_cfg)
            default_profile = "default"

        logger.info(
            "Initialized EmbeddingManager with profiles: %s (default=%s)",
            ", ".join(sorted(profiles.keys())),
            default_profile,
        )
        return cls(profiles=profiles, default_profile=default_profile)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def list_profiles(self) -> Sequence[str]:
        """Return the names of all configured embedding profiles."""
        return list(self._profiles.keys())

    def get_default_profile(self) -> str:
        """Return the name of the default embedding profile."""
        return self._default_profile

    def get_profile_metadata(self, profile: str | None = None) -> EmbeddingMetadata:
        """Return metadata for a profile (creating its provider if needed)."""
        provider = self._get_provider(profile)
        return provider.metadata

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _get_provider(self, profile: str | None = None) -> EmbeddingProvider:
        name = profile or self._default_profile

        if name not in self._profiles:
            raise EmbeddingConfigError(f"Unknown embedding profile '{name}'")

        with self._providers_lock:
            provider = self._providers.get(name)
            if provider is None:
                provider = create_provider_from_config(name, self._profiles[name].raw)
                self._providers[name] = provider
        return provider

    # ------------------------------------------------------------------
    # Public embedding API
    # ------------------------------------------------------------------

    def embed_passages(
        self,
        texts: Sequence[str],
        *,
        profile: str | None = None,
    ) -> list[list[float]]:
        provider = self._get_provider(profile)
        return provider.embed_passages(texts)

    def embed_queries(
        self,
        texts: Sequence[str],
        *,
        profile: str | None = None,
    ) -> list[list[float]]:
        provider = self._get_provider(profile)
        return provider.embed_queries(texts)

    def close(self) -> None:
        for provider in list(self._providers.values()):
            provider.close()
