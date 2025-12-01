"""
Enrichment Router – SDD v2.1 Phase 2+

Runtime data structures and routing logic for content-type-aware enrichment.

This module introduces:
  - EnrichmentSliceView: lightweight view of pending spans for routing decisions
  - EnrichmentRouteDecision: output of routing logic (chain, backends, reasons)
  - EnrichmentRouterMetricsEvent: JSONL metrics event shape
  - EnrichmentRouter: main routing orchestrator
  - build_router_from_toml: factory helper

See: DOCS/ROUTING/SDD_Enrichment_Router_v2_1.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any

from tools.rag.config_enrichment import (
    EnrichmentBackendSpec,
    EnrichmentConfig,
    EnrichmentConfigError,
    filter_chain_for_tier,
    load_enrichment_config,
    select_chain,
)

# -----------------------------------------------------------------------------
# 2.1.1 EnrichmentSliceView
# -----------------------------------------------------------------------------


@dataclass
class EnrichmentSliceView:
    """
    Lightweight view of a pending span used for routing decisions.

    Constructed from pending_enrichments rows (Database.pending_enrichments)
    and enrichment plan items (workers.enrichment_plan / execute_enrichment).

    Attributes:
        span_hash: Unique identifier for the span.
        file_path: Path to the source file containing the span.
        start_line: Starting line number (1-indexed).
        end_line: Ending line number (inclusive).
        content_type: Normalized type, e.g. "code", "docs", "erp_product", "unknown".
        classifier_confidence: Confidence score from content classifier (0.0-1.0).
        approx_token_count: Estimated token count for the span content.
        importance: Optional priority hint, e.g. "normal" or "high".
    """

    span_hash: str
    file_path: Path
    start_line: int
    end_line: int
    content_type: str
    classifier_confidence: float
    approx_token_count: int
    importance: str | None = None

    def __post_init__(self) -> None:
        # Normalize file_path to Path if passed as string
        if isinstance(self.file_path, str):
            object.__setattr__(self, "file_path", Path(self.file_path))


# -----------------------------------------------------------------------------
# 2.1.2 EnrichmentRouteDecision
# -----------------------------------------------------------------------------


@dataclass
class EnrichmentRouteDecision:
    """
    Represents the router's decision for a given slice.

    This is not persisted to DB; used for:
      - Logging (JSONL)
      - Building a BackendCascade for execution

    Attributes:
        slice_type: Normalized content type used for routing.
        chain_name: Selected chain name from [enrichment.routes] or default.
        backend_specs: Ordered list of backends in the selected chain.
        routing_tier: Tier label if tier-aware routing applied, e.g. "7b", "14b".
        reasons: Human-readable hints explaining the routing decision.
    """

    slice_type: str
    chain_name: str
    backend_specs: list[EnrichmentBackendSpec]
    routing_tier: str | None = None
    reasons: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# 2.1.3 EnrichmentRouterMetricsEvent
# -----------------------------------------------------------------------------


@dataclass
class EnrichmentRouterMetricsEvent:
    """
    Shape for JSONL metrics events emitted by the router.

    One event is emitted per backend attempt during cascade execution.
    """

    timestamp: float
    span_hash: str
    slice_type: str
    chain_name: str
    backend_name: str
    provider: str
    model: str | None
    routing_tier: str | None
    success: bool
    failure_type: str | None
    duration_sec: float
    attempt_index: int
    total_attempts: int
    reason: str | None = None
    extra: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for JSONL output."""
        return asdict(self)


# -----------------------------------------------------------------------------
# 4.4 Logging Helper
# -----------------------------------------------------------------------------


def _append_router_log(log_dir: Path, payload: dict[str, object]) -> None:
    """Append a metrics event to the router JSONL log.

    Args:
        log_dir: Directory containing logs (typically repo_root / "logs").
        payload: JSON-serializable dict to write.
    """
    log_path = log_dir / "enrichment_router_metrics.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")


# -----------------------------------------------------------------------------
# 4.1 EnrichmentRouter
# -----------------------------------------------------------------------------


class EnrichmentRouter:
    """
    Central router for content-type-aware enrichment chain selection.

    The router wraps an EnrichmentConfig and provides:
      - normalize_slice_type: canonical content type normalization
      - choose_chain: select chain based on slice_type and routes
      - build_cascade: construct BackendCascade from decision

    When routing is disabled (enable_routing=False or LLMC_ENRICH_DISABLE_ROUTING=1),
    the router always returns the default_chain, preserving Phase 1 shim behavior.
    """

    def __init__(
        self,
        config: EnrichmentConfig,
        *,
        enable_routing: bool,
        routes: Mapping[str, str] | None,
        max_tier: str | None = None,
        on_failure: str = "error",
        log_dir: Path | None = None,
    ) -> None:
        """
        Initialize the router.

        Args:
            config: Loaded EnrichmentConfig with chains.
            enable_routing: Whether to apply slice_type -> chain routing.
            routes: Mapping of slice_type -> chain_name.
            max_tier: Optional tier filter (e.g. "7b", "14b").
            on_failure: Policy when all backends fail: "error" or "fallback_to_empty".
            log_dir: Directory for JSONL metrics logs.
        """
        self.config = config
        self.enable_routing = enable_routing
        self.routes: dict[str, str] = dict(routes) if routes else {}
        self.max_tier = max_tier
        self.on_failure = on_failure
        self.log_dir = log_dir

    def normalize_slice_type(self, raw_type: str) -> str:
        """
        Normalize a raw content type to canonical form.

        Handles case normalization and common aliases.

        Args:
            raw_type: Raw content type string (e.g. "Code", "DOCS", "python").

        Returns:
            Normalized type (e.g. "code", "docs", "unknown").
        """
        if not raw_type:
            return "unknown"

        normalized = raw_type.strip().lower()
        if not normalized:
            return "unknown"

        # Common aliases
        aliases: dict[str, str] = {
            "python": "code",
            "javascript": "code",
            "typescript": "code",
            "java": "code",
            "rust": "code",
            "go": "code",
            "c": "code",
            "cpp": "code",
            "c++": "code",
            "markdown": "docs",
            "md": "docs",
            "rst": "docs",
            "text": "docs",
            "txt": "docs",
            "documentation": "docs",
            "erp": "erp_product",
            "product": "erp_product",
            "plan": "project_plan",
            "planning": "project_plan",
        }

        return aliases.get(normalized, normalized)

    def choose_chain(
        self,
        slice_view: EnrichmentSliceView,
        chain_override: str | None = None,
    ) -> EnrichmentRouteDecision:
        """
        Choose the enrichment chain for a given slice.

        Resolution order:
          1. chain_override (CLI --chain-name) if provided
          2. Routes map lookup (if enable_routing=True)
          3. config.default_chain (fallback)

        Args:
            slice_view: Slice metadata for routing decisions.
            chain_override: Optional explicit chain name override.

        Returns:
            EnrichmentRouteDecision with selected chain and backend specs.
        """
        reasons: list[str] = []
        slice_type = self.normalize_slice_type(slice_view.content_type)

        # 1. Explicit override takes precedence
        if chain_override:
            chain_name = chain_override
            reasons.append(f"chain_override={chain_override!r}")
        # 2. Route lookup when routing is enabled
        elif self.enable_routing and slice_type in self.routes:
            chain_name = self.routes[slice_type]
            reasons.append(f"route: {slice_type!r} -> {chain_name!r}")
        # 3. Fallback to default
        else:
            chain_name = self.config.default_chain
            if self.enable_routing:
                reasons.append(f"no route for {slice_type!r}, using default_chain")
            else:
                reasons.append("routing disabled, using default_chain")

        # Get backend specs for the chain
        try:
            backend_specs = select_chain(self.config, chain_name)
        except EnrichmentConfigError as exc:
            # Chain doesn't exist or has no enabled backends
            reasons.append(f"chain {chain_name!r} invalid: {exc}")
            backend_specs = select_chain(self.config, self.config.default_chain)
            chain_name = self.config.default_chain
            reasons.append(f"falling back to default_chain={chain_name!r}")

        # Apply tier filter if configured
        effective_tier: str | None = None
        if self.max_tier:
            filtered = filter_chain_for_tier(backend_specs, self.max_tier)
            if filtered:
                backend_specs = filtered
                effective_tier = self.max_tier
                reasons.append(f"filtered for max_tier={self.max_tier!r}")
            else:
                reasons.append(f"no backends match max_tier={self.max_tier!r}, using all")

        return EnrichmentRouteDecision(
            slice_type=slice_type,
            chain_name=chain_name,
            backend_specs=backend_specs,
            routing_tier=effective_tier,
            reasons=reasons,
        )

    def log_decision(self, decision: EnrichmentRouteDecision, span_hash: str) -> None:
        """
        Log a routing decision to the metrics JSONL file.

        Args:
            decision: The routing decision to log.
            span_hash: Hash of the span being routed.
        """
        if self.log_dir is None:
            return

        import time

        payload = {
            "timestamp": time.time(),
            "event_type": "route_decision",
            "span_hash": span_hash,
            "slice_type": decision.slice_type,
            "chain_name": decision.chain_name,
            "routing_tier": decision.routing_tier,
            "backend_count": len(decision.backend_specs),
            "reasons": decision.reasons,
        }
        _append_router_log(self.log_dir, payload)


# -----------------------------------------------------------------------------
# 4.1.2 Construction Helper
# -----------------------------------------------------------------------------


def build_router_from_toml(
    repo_root: Path,
    env: Mapping[str, str] | None = None,
    toml_path: Path | None = None,
) -> EnrichmentRouter:
    """
    Load EnrichmentConfig from llmc.toml + env and construct EnrichmentRouter.

    Args:
        repo_root: Repository root directory.
        env: Environment variables (defaults to os.environ).
        toml_path: Optional explicit path to TOML config.

    Returns:
        Configured EnrichmentRouter instance.

    Raises:
        EnrichmentConfigError: If configuration is invalid.
    """
    if env is None:
        env = os.environ

    config = load_enrichment_config(repo_root, toml_path=toml_path, env=env)

    # Check for env override to disable routing
    disable_routing_env = env.get("LLMC_ENRICH_DISABLE_ROUTING", "")
    force_disable = disable_routing_env.lower() in ("1", "true", "yes", "on")

    enable_routing = config.enable_routing and not force_disable

    log_dir = repo_root / "logs"

    return EnrichmentRouter(
        config=config,
        enable_routing=enable_routing,
        routes=config.routes,
        max_tier=config.max_tier,
        on_failure=config.on_failure,
        log_dir=log_dir,
    )


# -----------------------------------------------------------------------------
# Module exports
# -----------------------------------------------------------------------------

__all__ = [
    "EnrichmentSliceView",
    "EnrichmentRouteDecision",
    "EnrichmentRouterMetricsEvent",
    "EnrichmentRouter",
    "build_router_from_toml",
]
