from __future__ import annotations

import math

import pytest

from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from router import (
    RouterSettings,
    clamp_usage_snippet,
    choose_next_tier_on_failure,
    choose_start_tier,
    detect_truncation,
    estimate_json_nodes_and_depth,
    estimate_nesting_depth,
    estimate_tokens_from_text,
    expected_output_tokens,
)


def test_estimate_tokens_from_text():
    assert estimate_tokens_from_text("abcd") == 1
    assert estimate_tokens_from_text("a" * 400) == 100


def test_estimate_json_nodes_and_depth_parsed():
    text = '{"a": {"b": [1, 2, 3]}}'
    nodes, depth = estimate_json_nodes_and_depth(text)
    assert nodes >= 5
    assert depth >= 3


def test_estimate_json_nodes_and_depth_heuristic():
    text = '{foo: {bar: [1,2,3]}}'
    nodes, depth = estimate_json_nodes_and_depth(text)
    assert nodes >= 3
    assert depth >= 2


def test_estimate_nesting_depth():
    snippet = "function f() { if (true) { return { x: [1, 2] }; } }"
    assert estimate_nesting_depth(snippet) >= 3


def test_expected_output_tokens():
    span = {"code_snippet": "print('hello')"}
    tokens = expected_output_tokens(span)
    assert tokens >= 1200


def test_detect_truncation():
    truncated = '{"a": 1, "b": 2'
    assert detect_truncation(truncated, None, None)
    assert detect_truncation("{\"a\": 1}", None, "length")
    assert not detect_truncation("{\"a\": 1}", None, "stop")


def test_choose_start_tier_small_span():
    settings = RouterSettings()
    metrics = {
        "line_count": 30,
        "nesting_depth": 2,
        "tokens_in": 1000,
        "tokens_out": 1200,
    }
    assert choose_start_tier(metrics, settings, override="auto") == "7b"


def test_choose_start_tier_medium_span():
    settings = RouterSettings()
    metrics = {
        "line_count": 80,
        "nesting_depth": 2,
        "tokens_in": 3000,
        "tokens_out": 1500,
    }
    assert choose_start_tier(metrics, settings) == "14b"


def test_choose_start_tier_large_span_to_nano():
    settings = RouterSettings()
    metrics = {
        "line_count": 120,
        "nesting_depth": 4,
        "tokens_in": settings.effective_token_limit + 1000,
        "tokens_out": 500,
    }
    assert choose_start_tier(metrics, settings) == "nano"


def test_choose_next_tier_on_truncation():
    settings = RouterSettings()
    tier = choose_next_tier_on_failure("truncation", "7b", {}, settings)
    assert tier == "nano"


def test_choose_next_tier_parse_then_validation():
    settings = RouterSettings()
    tier = choose_next_tier_on_failure("parse", "7b", {}, settings)
    assert tier == "14b"
    tier2 = choose_next_tier_on_failure("validation", "14b", {}, settings)
    assert tier2 == "nano"


def test_clamp_usage_snippet():
    result = {
        "usage_snippet": "\n".join(str(i) for i in range(20))
    }
    clamp_usage_snippet(result, max_lines=12)
    assert len(result["usage_snippet"].splitlines()) == 12
