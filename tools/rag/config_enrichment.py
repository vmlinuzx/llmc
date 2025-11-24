from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

import os
import json

try:  # Python 3.11+
    import tomllib as _toml  # type: ignore[import]
except Exception:  # pragma: no cover - fallback for older runtimes
    try:
        import tomli as _toml  # type: ignore[import]
    except Exception as exc:  # pragma: no cover
        _toml = None  # type: ignore[assignment]


_ALLOWED_PROVIDERS = {"ollama", "gateway", "gemini"}
_ALLOWED_TIERS = {"7b", "14b", "nano"}


@dataclass
class EnrichmentBackendSpec:
    """Single backend entry in an enrichment chain."""

    name: str
    chain: str = "default"
    provider: str = "ollama"
    model: str | None = None
    url: str | None = None
    routing_tier: str | None = None
    timeout_seconds: int | None = None
    options: dict[str, Any] | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.options is None:
            self.options = {}


@dataclass
class EnrichmentConfig:
    """Resolved enrichment configuration."""

    default_chain: str
    concurrency: int
    cooldown_seconds: int
    batch_size: int
    max_retries_per_span: int
    enforce_latin1_enrichment: bool
    chains: dict[str, list[EnrichmentBackendSpec]]


class EnrichmentConfigError(ValueError):
    """Raised when enrichment configuration is invalid."""


BackendConfig = EnrichmentBackendSpec

__all__ = [
    "EnrichmentBackendSpec",
    "BackendConfig",
    "EnrichmentConfig",
    "EnrichmentConfigError",
    "load_enrichment_config",
]

# Backwards-compat alias for older code/tests referencing BackendConfig
BackendConfig = EnrichmentBackendSpec

__all__ = [
    "EnrichmentBackendSpec",
    "BackendConfig",
    "EnrichmentConfig",
    "EnrichmentConfigError",
    "load_enrichment_config",
]

def _load_toml(path: Path) -> dict[str, Any]:
    if _toml is None:
        raise EnrichmentConfigError("No TOML parser available (tomllib/tomli not installed).")
    with path.open("rb") as f:
        return _toml.load(f)


def _parse_backend_spec(
    raw: Mapping[str, Any],
    *,
    default_chain: str,
) -> EnrichmentBackendSpec:
    name = str(raw.get("name") or "").strip()
    if not name:
        raise EnrichmentConfigError("enrichment.chain entry is missing a non-empty 'name'.")

    chain_name = str(raw.get("chain") or default_chain)
    provider = str(raw.get("provider") or "").strip()
    if provider not in _ALLOWED_PROVIDERS:
        raise EnrichmentConfigError(f"Unsupported enrichment provider {provider!r} for backend {name!r}.")

    model = raw.get("model")
    if model is not None:
        model = str(model)

    url = raw.get("url")
    if url is not None:
        url = str(url)

    routing_tier = raw.get("routing_tier")
    if routing_tier is not None:
        routing_tier = str(routing_tier)
        if routing_tier not in _ALLOWED_TIERS:
            raise EnrichmentConfigError(
                f"Invalid routing_tier {routing_tier!r} for backend {name!r}; "
                f"expected one of {_ALLOWED_TIERS!r}."
            )

    timeout_seconds_raw = raw.get("timeout_seconds")
    timeout_seconds: int | None
    if timeout_seconds_raw is None:
        timeout_seconds = None
    else:
        try:
            timeout_seconds = int(timeout_seconds_raw)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise EnrichmentConfigError(
                f"Invalid timeout_seconds={timeout_seconds_raw!r} for backend {name!r}."
            ) from exc

    options_raw = raw.get("options") or {}
    if not isinstance(options_raw, Mapping):
        raise EnrichmentConfigError(
            f"enrichment.chain.options for backend {name!r} must be a mapping, not {type(options_raw)!r}."
        )
    options = dict(options_raw)

    enabled_raw = raw.get("enabled", True)
    enabled = bool(enabled_raw)

    return EnrichmentBackendSpec(
        name=name,
        chain=chain_name,
        provider=provider,
        model=model,
        url=url,
        routing_tier=routing_tier,
        timeout_seconds=timeout_seconds,
        options=options,
        enabled=enabled,
    )


def _parse_chain_from_toml(
    data: Mapping[str, Any],
    *,
    default_chain: str,
) -> dict[str, list[EnrichmentBackendSpec]]:
    chains: dict[str, list[EnrichmentBackendSpec]] = {}
    root_enrichment = data.get("enrichment") or {}
    chain_entries = root_enrichment.get("chain") or []
    if isinstance(chain_entries, Mapping):
        chain_entries = [chain_entries]

    for raw in chain_entries:
        if not isinstance(raw, Mapping):
            continue
        spec = _parse_backend_spec(raw, default_chain=default_chain)
        chains.setdefault(spec.chain, []).append(spec)

    return chains


def _parse_chain_from_json(
    json_str: str,
    *,
    default_chain: str,
) -> dict[str, list[EnrichmentBackendSpec]]:
    """Parse chain definitions from ENRICH_CHAIN_JSON.

    Supported shapes:

    - A list of backend objects, each with at least ``name`` and ``provider``.
    - A dict with ``"chains"`` mapping chain name -> list of backend objects.
    """
    try:
        payload = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise EnrichmentConfigError(f"Failed to parse ENRICH_CHAIN_JSON: {exc}") from exc

    chains: dict[str, list[EnrichmentBackendSpec]] = {}

    if isinstance(payload, list):
        specs_raw = payload
        for raw in specs_raw:
            if not isinstance(raw, Mapping):
                continue
            spec = _parse_backend_spec(raw, default_chain=default_chain)
            chains.setdefault(spec.chain, []).append(spec)
        return chains

    if isinstance(payload, Mapping) and "chains" in payload:
        chains_raw = payload.get("chains") or {}
        if not isinstance(chains_raw, Mapping):
            raise EnrichmentConfigError("ENRICH_CHAIN_JSON['chains'] must be a mapping.")
        for chain_name, entries in chains_raw.items():
            if not isinstance(entries, list):
                continue
            for raw in entries:
                if not isinstance(raw, Mapping):
                    continue
                raw = dict(raw)
                raw.setdefault("chain", chain_name)
                spec = _parse_backend_spec(raw, default_chain=default_chain)
                chains.setdefault(spec.chain, []).append(spec)
        return chains

    raise EnrichmentConfigError(
        "ENRICH_CHAIN_JSON must be either a list of backend entries or "
        "a dict with a 'chains' mapping."
    )


def load_enrichment_config(
    repo_root: Path,
    *,
    toml_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> EnrichmentConfig:
    """Load enrichment configuration from TOML + environment.

    The resolution order is:

    1. TOML at ``toml_path`` or ``repo_root / "llmc.toml"`` (if present).
    2. Environment overrides:
       - ENRICH_CHAIN_JSON
       - ENRICH_CONCURRENCY
       - ENRICH_COOLDOWN_SECONDS
       - ENRICH_BATCH_SIZE
       - ENRICH_MAX_RETRIES_PER_SPAN
    3. Hard-coded defaults when TOML is missing.
    """
    if env is None:
        env = os.environ

    # Determine TOML path, if any.
    cfg_path: Path | None = None
    if toml_path is not None:
        cfg_path = toml_path if toml_path.is_absolute() else (repo_root / toml_path)
    else:
        candidate = repo_root / "llmc.toml"
        if candidate.exists():
            cfg_path = candidate

    data: dict[str, Any] = {}
    if cfg_path is not None and cfg_path.exists():
        data = _load_toml(cfg_path)

    root_enrichment = data.get("enrichment") or {}
    default_chain = str(root_enrichment.get("default_chain") or "default")

    # Concurrency / cooldown with env overrides.
    concurrency_raw = env.get("ENRICH_CONCURRENCY", root_enrichment.get("concurrency", 1))
    try:
        concurrency = int(concurrency_raw)
    except (TypeError, ValueError):
        concurrency = 1

    cooldown_raw = env.get("ENRICH_COOLDOWN_SECONDS", root_enrichment.get("cooldown_seconds", 0))
    try:
        cooldown_seconds = int(cooldown_raw)
    except (TypeError, ValueError):
        cooldown_seconds = 0
    # Batch size and per-span retry defaults with env overrides.
    batch_size_raw = env.get("ENRICH_BATCH_SIZE", root_enrichment.get("batch_size", 5))
    try:
        batch_size = int(batch_size_raw)
    except (TypeError, ValueError):
        batch_size = 5

    max_retries_raw = env.get(
        "ENRICH_MAX_RETRIES_PER_SPAN",
        root_enrichment.get("max_retries_per_span", 3),
    )
    try:
        max_retries_per_span = int(max_retries_raw)
    except (TypeError, ValueError):
        max_retries_per_span = 3

    enforce_latin1_raw = env.get(
        "ENRICH_ENFORCE_LATIN1",
        root_enrichment.get("enforce_latin1_enrichment", True),
    )
    enforce_latin1_enrichment = str(enforce_latin1_raw).lower() in ("1", "true", "yes", "on")


    # Chains from TOML.
    chains = _parse_chain_from_toml(data, default_chain=default_chain)

    # Optional JSON override.
    json_override = env.get("ENRICH_CHAIN_JSON")
    if json_override:
        json_chains = _parse_chain_from_json(json_override, default_chain=default_chain)
        # JSON is considered a replacement for TOML definitions for the chains it defines.
        for name, specs in json_chains.items():
            chains[name] = specs

    # No TOML, no JSON, no chains: construct a minimal default config.
    if not chains:
        url = env.get("ATHENA_OLLAMA_URL", "http://localhost:11434")
        spec = EnrichmentBackendSpec(
            name="default-ollama-7b",
            chain=default_chain,
            provider="ollama",
            model=None,
            url=url,
            routing_tier="7b",
            timeout_seconds=None,
            options={},
            enabled=True,
        )
        chains = {default_chain: [spec]}

    # Validate default chain has at least one enabled entry.
    default_entries = [s for s in chains.get(default_chain, []) if s.enabled]
    if not default_entries:
        raise EnrichmentConfigError(
            f"No enabled enrichment backends found for default chain {default_chain!r}."
        )

    return EnrichmentConfig(
        default_chain=default_chain,
        concurrency=concurrency,
        cooldown_seconds=cooldown_seconds,
        batch_size=batch_size,
        max_retries_per_span=max_retries_per_span,
        enforce_latin1_enrichment=enforce_latin1_enrichment,
        chains=chains,
    )


def select_chain(
    config: EnrichmentConfig,
    chain_name: str | None,
) -> list[EnrichmentBackendSpec]:
    """Return the ordered, enabled backends for a given chain name."""
    effective_name = chain_name or config.default_chain
    entries = config.chains.get(effective_name, [])
    enabled_entries = [s for s in entries if s.enabled]
    if not enabled_entries:
        raise EnrichmentConfigError(f"No enabled entries for enrichment chain {effective_name!r}.")
    return enabled_entries


def filter_chain_for_tier(
    chain: Sequence[EnrichmentBackendSpec],
    routing_tier: str,
) -> list[EnrichmentBackendSpec]:
    """Filter a chain for a specific router tier.

    Rules (Phase 5):

    - Include entries whose ``routing_tier`` exactly matches ``routing_tier``.
    - Additionally, for routing_tier == "7b", include entries with routing_tier is None.
    """
    if routing_tier not in _ALLOWED_TIERS:
        raise EnrichmentConfigError(f"Unknown routing_tier {routing_tier!r}.")

    filtered: list[EnrichmentBackendSpec] = []
    for spec in chain:
        tier = spec.routing_tier
        if tier is None and routing_tier == "7b":
            filtered.append(spec)
        elif tier == routing_tier:
            filtered.append(spec)
    return filtered