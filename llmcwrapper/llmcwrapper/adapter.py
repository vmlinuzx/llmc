# llmcwrapper/adapter.py
from __future__ import annotations
from typing import Any, Dict
from .config import load_resolved_config, ensure_run_snapshot
from .rag_client import HttpRAG
from .providers import get_provider_driver
from .capabilities import CAPABILITIES
from .telemetry import log_event, new_corr_id
from .costs import estimate_cost
from .util import info, yellow

class AdapterError(Exception):
    pass

def _invariants(mode: str, resolved: Dict[str, Any], force: bool=False):
    profile = resolved.get("defaults", {}).get("profile") or resolved.get("__run__", {}).get("profile")
    prof = resolved["profiles"][profile]
    rag_enabled = bool(prof.get("rag", {}).get("enabled", False))
    tools_enabled = bool(prof.get("tools", {}).get("enabled", False))
    rag_server = prof.get("rag", {}).get("server")

    if mode == "yolo":
        if rag_enabled or tools_enabled:
            msg = "yolo requires rag.enabled=false and tools.enabled=false"
            if force: info(yellow("[WARN] " + msg + " (force)"))
            else: raise AdapterError(msg)
    elif mode == "rag":
        if not rag_enabled:
            msg = "rag requires rag.enabled=true"
            if force: info(yellow("[WARN] " + msg + " (force)"))
            else: raise AdapterError(msg)
        if rag_server:
            client = HttpRAG()
            try:
                client.head(rag_server, timeout=2)
            except Exception as e:
                msg = f"RAG server not reachable: {e}"
                if force: info(yellow("[WARN] " + msg + " (force)"))
                else: raise AdapterError(msg)
    else:
        raise AdapterError(f"Unknown mode: {mode}")

def send(messages, *, tools=None, max_tokens=None, temperature=None, model=None, correlation_id=None,
         mode="yolo", profile="daily", overlays=None, sets=None, unsets=None, force=False, dry_run=False):
    # Resolve config
    resolved = load_resolved_config(profile=profile, mode=mode, overlays=overlays, sets=sets, unsets=unsets)
    corr_id = correlation_id or new_corr_id()
    resolved.setdefault("__run__", {})["profile"] = profile

    # Snapshot + telemetry start
    snap = ensure_run_snapshot(resolved, corr_id)
    log_event(".", corr_id, "start", {"mode": mode, "profile": profile, "snapshot": snap})

    # Invariants
    _invariants(mode, resolved, force=force)

    prof = resolved["profiles"][profile]
    provider = prof["provider"]
    model_name = model or prof.get("model")
    temp = temperature if temperature is not None else prof.get("temperature", 0.2)

    # Capabilities sanity (cheap assertions)
    caps = CAPABILITIES.get(provider, {})
    if tools and not caps.get("tools", False):
        if not force:
            raise AdapterError(f"Provider '{provider}' does not support tools (pass --force to override)")

    if dry_run:
        log_event(".", corr_id, "dry_run", {"provider": provider, "model": model_name})
        return {"message": {"role":"assistant","content":"[dry-run] no call executed"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "finish_reason": "dry_run",
                "provider": provider, "model": model_name, "corr_id": corr_id}

    # Dispatch to provider
    driver = get_provider_driver(provider)
    log_event(".", corr_id, "provider_request_meta", {"provider": provider, "model": model_name})
    result = driver.send(messages=messages, tools=tools, max_tokens=max_tokens, temperature=temp,
                         model=model_name, correlation_id=corr_id, profile_cfg=prof, resolved_cfg=resolved)

    usage = result.get("usage", {}) or {}
    price_cfg = resolved.get("pricing", {})
    est = estimate_cost(provider, model_name, usage.get("input_tokens"), usage.get("output_tokens"), price_cfg)
    log_event(".", corr_id, "cost_estimate", {"usd": est, "usage": usage})

    return {**result, "provider": provider, "model": model_name, "corr_id": corr_id}
