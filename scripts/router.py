"""Routing helpers for enrichment model selection."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple


def estimate_tokens_from_text(text: str) -> int:
    """Rough token estimate (~4 characters per token)."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _walk_json(obj: object, depth: int = 1) -> Tuple[int, int]:
    """Return (node_count, max_depth) for parsed JSON objects."""
    if isinstance(obj, dict):
        count = 1
        max_depth = depth
        for value in obj.values():
            child_count, child_depth = _walk_json(value, depth + 1)
            count += child_count
            max_depth = max(max_depth, child_depth)
        return count, max_depth
    if isinstance(obj, (list, tuple)):
        count = 1
        max_depth = depth
        for value in obj:
            child_count, child_depth = _walk_json(value, depth + 1)
            count += child_count
            max_depth = max(max_depth, child_depth)
        return count, max_depth
    return 1, depth


def estimate_json_nodes_and_depth(text: str) -> Tuple[int, int]:
    """Estimate number of JSON nodes and depth from text.

    Attempts to parse the text as JSON first; on failure falls back to a
    lightweight brace counting heuristic.
    """

    if not text:
        return 0, 0

    try:
        parsed = json.loads(text)
    except Exception:
        node_count = 0
        depth = 0
        current = 0
        for ch in text:
            if ch in "{[":
                current += 1
                depth = max(depth, current)
                node_count += 1
            elif ch in "}]" and current:
                current -= 1
        return node_count, depth

    count, depth = _walk_json(parsed)
    return count, depth


def estimate_nesting_depth(snippet: str) -> int:
    """Estimate generic nesting depth using braces/brackets/parentheses."""
    if not snippet:
        return 0

    pairs = {"}": "{", "]": "[", ")": "("}
    stack: list[str] = []
    max_depth = 0
    for ch in snippet:
        if ch in "{[()":
            stack.append(ch)
            max_depth = max(max_depth, len(stack))
        elif ch in pairs:
            while stack and stack[-1] != pairs[ch]:
                stack.pop()
            if stack:
                stack.pop()
    return max_depth


def expected_output_tokens(span: Dict[str, object]) -> int:
    """Estimate output tokens for enrichment JSON response."""
    base_fields = 6  # summary, inputs, outputs, side_effects, pitfalls, usage_snippet
    keys = int(span.get("estimated_fields", base_fields) or base_fields)
    snippet = span.get("code_snippet", "") or ""
    approx_values = estimate_tokens_from_text(snippet) // 2
    estimate = (keys * 6) + approx_values
    return max(estimate, 1200)


def detect_truncation(output_text: str, max_tokens_used: Optional[int], finish_reason: Optional[str]) -> bool:
    """Heuristically detect truncated JSON output."""
    if finish_reason and finish_reason.lower() in {"length", "max_tokens", "token_limit"}:
        return True
    if not output_text:
        return False
    opens = output_text.count("{")
    closes = output_text.count("}")
    if closes < opens and opens - closes > 1:
        return True
    stripped = output_text.rstrip()
    if stripped and stripped[-1] not in "}]" and stripped[-1] != '"':
        return True
    if max_tokens_used is not None and max_tokens_used <= 0:
        return True
    return False


@dataclass
class RouterSettings:
    """Tunable thresholds for routing decisions."""

    context_limit: int = 32000
    headroom: int = 4000
    preflight_limit: int = 28000
    node_limit: int = 800
    depth_limit: int = 6
    array_limit: int = 5000
    csv_limit: int = 60
    nesting_limit: int = 3
    line_thresholds: Tuple[int, int] = None  # type: ignore

    def __post_init__(self) -> None:
        def _read_int_env(name: str, current: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return current
            try:
                return int(raw)
            except Exception:
                return current

        self.context_limit = _read_int_env("ROUTER_CONTEXT_LIMIT", self.context_limit)
        self.headroom = _read_int_env(
            "ROUTER_MAX_TOKENS_HEADROOM", self.headroom
        )
        self.preflight_limit = _read_int_env(
            "ROUTER_PRE_FLIGHT_LIMIT", self.preflight_limit
        )
        self.node_limit = _read_int_env("ROUTER_NODE_LIMIT", self.node_limit)
        self.depth_limit = _read_int_env("ROUTER_DEPTH_LIMIT", self.depth_limit)
        self.array_limit = _read_int_env("ROUTER_ARRAY_LIMIT", self.array_limit)
        self.csv_limit = _read_int_env("ROUTER_CSV_LIMIT", self.csv_limit)
        self.nesting_limit = _read_int_env(
            "ROUTER_NESTING_LIMIT", self.nesting_limit
        )

        thresholds = os.getenv("ROUTER_LINE_THRESHOLDS", "60,100")
        try:
            low, high = [int(part.strip()) for part in thresholds.split(",", 1)]
        except Exception:
            low, high = 60, 100
        if low <= 0 or high <= 0:
            low, high = 60, 100
        if low > high:
            low, high = high, low
        self.line_thresholds = (low, high)

    @property
    def effective_token_limit(self) -> int:
        context_cap = max(1, self.context_limit - self.headroom)
        return min(self.preflight_limit, context_cap)


def choose_start_tier(metrics: Dict[str, float], settings: RouterSettings, override: str | None = None) -> str:
    """Choose initial tier based on metrics and overrides."""

    override = (override or os.getenv("ROUTER_DEFAULT_TIER", "auto")).lower()
    valid_tiers = {"auto", "7b", "14b", "nano"}
    if override not in valid_tiers:
        override = "auto"
    if override != "auto":
        return override

    tokens_total = metrics.get("tokens_in", 0) + metrics.get("tokens_out", 0)
    node_count = metrics.get("node_count", 0)
    schema_depth = metrics.get("schema_depth", 0)
    array_elements = metrics.get("array_elements", 0)
    csv_columns = metrics.get("csv_columns", 0)

    if tokens_total > settings.effective_token_limit:
        return "nano"
    if node_count > settings.node_limit or schema_depth > settings.depth_limit:
        return "nano"
    if array_elements > settings.array_limit or csv_columns > settings.csv_limit:
        return "nano"

    line_count = metrics.get("line_count", 0)
    nesting_depth = metrics.get("nesting_depth", 0)

    low, high = settings.line_thresholds

    if line_count > high:
        return "14b"
    if line_count > low or nesting_depth > settings.nesting_limit:
        tier = "14b"
    else:
        tier = "7b"

    rag_k = metrics.get("rag_k")
    rag_avg = metrics.get("rag_avg_score")
    if rag_k == 0 or (rag_avg is not None and rag_avg < 0.25):
        if tier == "7b":
            tier = "14b"

    return tier


def choose_next_tier_on_failure(
    failure_type: str,
    current_tier: str,
    metrics: Dict[str, float],
    settings: RouterSettings,
    promote_once: bool = True,
) -> Optional[str]:
    failure_type = failure_type.lower()

    if current_tier == "nano":
        return None

    if failure_type == "truncation":
        return "nano"

    if current_tier == "7b":
        if failure_type in {"parse", "validation", "no_evidence"}:
            return "14b"
        return "nano"

    if current_tier == "14b":
        return "nano"

    if promote_once:
        return "nano"
    return None


def classify_failure(failure: Tuple[str, object, object]) -> str:
    failure_type = failure[0] if failure else "unknown"
    return str(failure_type)


def clamp_usage_snippet(result: Dict[str, object], max_lines: int = 12) -> None:
    snippet = result.get("usage_snippet")
    if not isinstance(snippet, str):
        return
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return
    result["usage_snippet"] = "\n".join(lines[:max_lines])
