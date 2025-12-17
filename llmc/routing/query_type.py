from __future__ import annotations

from typing import Any

from . import code_heuristics as ch, erp_heuristics as eh
from .common import load_routing_config, record_decision


def classify_query(
    text: str | None, tool_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return a deterministic classification for a query."""
    reasons: list[str] = []
    route_name = "docs"
    confidence = 0.5

    # Normalize
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        return {
            "route_name": "docs",
            "confidence": 0.2,
            "reasons": ["empty-or-none-input"],
        }

    # 1. Tool/context hint (highest priority) - Phase 4 Bugfix
    if tool_context and "tool_id" in tool_context:
        raw_tool_id = tool_context["tool_id"]
        if raw_tool_id:
            tool_id = raw_tool_id.lower()
            if "code" in tool_id or "refactor" in tool_id or "analyze" in tool_id:
                return {
                    "route_name": "code",
                    "confidence": 1.0,
                    "reasons": ["tool-context=code"],
                }
            elif "erp" in tool_id or "product" in tool_id or "lookup" in tool_id:
                return {
                    "route_name": "erp",
                    "confidence": 1.0,
                    "reasons": ["tool-context=erp"],
                }

    # Load config
    cfg = load_routing_config()

    # Evaluate signals
    code_sig = ch.score_all(text, cfg.get("code_detection"))
    erp_sig = eh.score_all(text, cfg.get("erp_vs_code"))

    # Policy
    policy = cfg.get("erp_vs_code", {})
    prefer_code = bool(policy.get("prefer_code_on_conflict", True))
    conflict_margin = float(policy.get("conflict_margin", 0.1))

    # Decide
    if code_sig and not erp_sig:
        route_name, confidence = code_sig.route, code_sig.score
        reasons.append(code_sig.reason)
    elif erp_sig and not code_sig:
        route_name, confidence = erp_sig.route, erp_sig.score
        reasons.append(erp_sig.reason)
    elif code_sig and erp_sig:
        if abs(code_sig.score - erp_sig.score) <= conflict_margin:
            if prefer_code:
                route_name, confidence = code_sig.route, max(code_sig.score, 0.8)
                reasons.append("conflict-policy:prefer-code")
                reasons.append(code_sig.reason)
            else:
                route_name, confidence = erp_sig.route, max(erp_sig.score, 0.8)
                reasons.append("conflict-policy:prefer-erp")
                reasons.append(erp_sig.reason)
        elif code_sig.score > erp_sig.score:
            route_name, confidence = code_sig.route, code_sig.score
            reasons.append("conflict-policy:code-stronger")
            reasons.append(code_sig.reason)
        else:
            route_name, confidence = erp_sig.route, erp_sig.score
            reasons.append("conflict-policy:erp-stronger")
            reasons.append(erp_sig.reason)
    else:
        route_name = cfg.get("default_route", "docs")
        reasons.append("default=docs")

    # Metrics/log
    record_decision(
        route_name=route_name,
        confidence=confidence,
        reasons=reasons,
        flags={
            "has_code": bool(code_sig),
            "has_erp": bool(erp_sig),
            "text_len": len(text),
        },
    )
    return {
        "route_name": route_name,
        "confidence": confidence,
        "reasons": reasons,
    }


# Backward compatibility exports for legacy test modules
# TODO: Update legacy tests to use new names and remove these aliases in a future cleanup phase
