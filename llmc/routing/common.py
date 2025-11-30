
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None

@dataclass
class RouteSignal:
    route: str
    score: float
    reason: str

def load_routing_config(start_dir: Path | None = None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "default_route": "docs",
        "code_detection": {},
        "erp_vs_code": {},
    }
    if tomllib is None:
        return cfg
    base = start_dir or Path.cwd()
    for parent in [base, *base.parents]:
        cand = parent / "llmc.toml"
        if cand.exists():
            try:
                with cand.open("rb") as f:
                    data = tomllib.load(f) or {}
                routing = data.get("routing", {})
                cfg.update({
                    "default_route": routing.get("default_route", cfg["default_route"]),
                    "code_detection": routing.get("code_detection", cfg["code_detection"]) or {},
                    "erp_vs_code": routing.get("erp_vs_code", cfg["erp_vs_code"]) or {},
                })
            except Exception:
                pass
            break
    return cfg

def record_decision(route_name: str, confidence: float, reasons: list[str], flags: Dict[str, Any]) -> None:
    logger = logging.getLogger("llmc.routing")
    payload = {
        "event": "routing_decision",
        "route_name": route_name,
        "confidence": confidence,
        "reasons": reasons,
        **flags,
    }
    try:
        logger.info("routing_decision %s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
