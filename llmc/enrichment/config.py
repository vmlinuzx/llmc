from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

DEFAULT_PATH_WEIGHT: int = 5
MIN_PATH_WEIGHT: int = 1
MAX_PATH_WEIGHT: int = 10

log = logging.getLogger(__name__)


def validate_path_weight(weight: int) -> int:
    """
    Validate a single path weight value.

    Raises:
        ValueError: If the weight is outside the allowed range.
    """
    if not MIN_PATH_WEIGHT <= weight <= MAX_PATH_WEIGHT:
        raise ValueError(
            f"Path weight must be between {MIN_PATH_WEIGHT} and {MAX_PATH_WEIGHT}, got {weight}"
        )
    return weight


def load_path_weight_map(config: Mapping[str, Any] | None) -> dict[str, int]:
    """
    Load the path weight mapping from a parsed llmc.toml config.

    The expected TOML structure is:

    [enrichment.path_weights]
    "src/**" = 1
    "**/tests/**" = 6
    "docs/**" = 8

    Args:
        config: Parsed llmc.toml dictionary (may be empty or None).

    Returns:
        A mapping of glob pattern -> validated weight (1-10).
    """
    weights: dict[str, int] = {}

    if config is None:
        return weights

    root = config.get("enrichment") or {}
    raw_weights = root.get("path_weights") or {}
    if not isinstance(raw_weights, Mapping):
        return weights
    for pattern, raw in raw_weights.items():
        try:
            value = int(raw)
        except (TypeError, ValueError):
            log.warning(
                "Ignoring non-integer path weight %r for pattern %r", raw, pattern
            )
            continue

        try:
            validated = validate_path_weight(value)
        except ValueError as exc:
            # Defensive: clamp out-of-range values instead of failing hard.
            log.warning("Adjusting invalid path weight for %r: %s", pattern, exc)
            validated = max(MIN_PATH_WEIGHT, min(MAX_PATH_WEIGHT, value))

        weights[str(pattern)] = validated

    return weights


__all__ = [
    "DEFAULT_PATH_WEIGHT",
    "MIN_PATH_WEIGHT",
    "MAX_PATH_WEIGHT",
    "validate_path_weight",
    "load_path_weight_map",
]
