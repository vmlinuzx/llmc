
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

from .common import RouteSignal, load_routing_config, record_decision
from . import code_heuristics as ch
from . import erp_heuristics as eh

def classify_query(text: Optional[str], tool_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a deterministic classification for a query."""
    reasons: List[str] = []
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
