from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from llmc.rag.types import SpanWorkItem

from .config import DEFAULT_PATH_WEIGHT

BASE_PRIORITY_CODE: int = 100
BASE_PRIORITY_NON_CODE: int = 10


@dataclass(frozen=True)
class PathWeightDecision:
    """Decision details for a single file path."""

    path: str
    weight: int
    matched_patterns: Sequence[str]
    winning_pattern: str | None
    base_priority: float
    final_priority: float


def get_path_weight(
    file_path: str,
    weight_config: Mapping[str, int],
    default_weight: int = DEFAULT_PATH_WEIGHT,
) -> tuple[int, list[str], str | None]:
    """
    Compute the path weight for a given repo-relative file path.

    Collision rule: highest weight wins.

    Args:
        file_path: Repo-relative path using POSIX separators.
        weight_config: Mapping of glob pattern -> weight.
        default_weight: Fallback when no patterns match.

    Returns:
        (final_weight, matched_patterns, winning_pattern)
    """
    posix_path = file_path.replace("\\", "/")
    matches: list[tuple[str, int]] = []

    for pattern, weight in weight_config.items():
        if fnmatchcase(posix_path, pattern):
            matches.append((pattern, int(weight)))

    if not matches:
        return default_weight, [], None

    winning_pattern, winning_weight = max(matches, key=lambda item: item[1])
    matched_patterns = [pattern for pattern, _ in matches]
    return winning_weight, matched_patterns, winning_pattern


def classify_content_type(slice_type: str | None) -> tuple[str, int]:
    """
    Map slice_type into a coarse content class and base priority.

    For now we distinguish only CODE vs NON_CODE to keep this
    component focused on path weights. The runner can layer on
    additional modifiers later.
    """
    if not slice_type:
        return "unknown", BASE_PRIORITY_NON_CODE

    normalized = slice_type.strip().lower()
    if not normalized:
        return "unknown", BASE_PRIORITY_NON_CODE

    if normalized == "code":
        return "code", BASE_PRIORITY_CODE
    if normalized in {"docs", "documentation"}:
        return "docs", BASE_PRIORITY_NON_CODE

    # Any other content types (config, unknown, etc.) are treated as non-code.
    return normalized, BASE_PRIORITY_NON_CODE


def compute_final_priority(base_priority: float, weight: int) -> float:
    """
    Apply the path-weight multiplier to a base priority.

    Formula from SDD_Enrichment_Path_Weights:
        final = base * (11 - weight) / 10
    """
    return base_priority * (11 - float(weight)) / 10.0


@dataclass
class FileClassifier:
    """
    Classify enrichment work items using path weights.

    This is intentionally lightweight and stateless beyond
    the configured weight mapping so it can be reused by the
    code-first scheduler and CLI dry-run tooling.
    """

    repo_root: Path
    weight_config: Mapping[str, int]
    default_weight: int = DEFAULT_PATH_WEIGHT

    def classify_span(self, item: SpanWorkItem) -> PathWeightDecision:
        """
        Classify a single span work item.

        Args:
            item: Pending enrichment work item from the DB.

        Returns:
            PathWeightDecision with weight and priority details.
        """
        # Database stores repo-relative paths; normalize them to POSIX.
        rel_path = str(item.file_path)
        weight, matched, winning = get_path_weight(
            rel_path, self.weight_config, default_weight=self.default_weight
        )

        _, base = classify_content_type(item.slice_type)
        final = compute_final_priority(base, weight)

        return PathWeightDecision(
            path=rel_path,
            weight=weight,
            matched_patterns=tuple(matched),
            winning_pattern=winning,
            base_priority=base,
            final_priority=final,
        )

    def classify_spans(self, items: Iterable[SpanWorkItem]) -> list[PathWeightDecision]:
        """Classify a sequence of span work items."""
        return [self.classify_span(item) for item in items]


__all__ = [
    "PathWeightDecision",
    "FileClassifier",
    "get_path_weight",
    "classify_content_type",
    "compute_final_priority",
]

