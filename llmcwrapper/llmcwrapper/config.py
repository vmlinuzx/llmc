# llmcwrapper/config.py
from __future__ import annotations
import os, json, copy, time
from typing import Any, Dict, List, Tuple

try:
    import tomllib  # 3.11+
except ModuleNotFoundError:
    tomllib = None
try:
    import tomli
except ModuleNotFoundError:
    tomli = None

DICT = Dict[str, Any]

DEFAULTS = {
    "defaults": {"profile": "daily", "mode": "yolo"},
    "profiles": {
        "daily": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-latest",
            "temperature": 0.3,
            "rag": {"enabled": True, "server": "http://127.0.0.1:8077"},
            "tools": {"enabled": True}
        },
        "yolo": {
            "provider": "minimax",
            "model": "m2-lite",
            "temperature": 0.2,
            "rag": {"enabled": False},
            "tools": {"enabled": False}
        }
    },
    "providers": {
        "anthropic": {"base_url": "https://api.anthropic.com/v1/messages", "env_key": "ANTHROPIC_API_KEY", "wire_api": "messages", "anthropic_version": "2023-06-01"},
        "minimax": {"base_url": "https://api.minimax.chat", "env_key": "MINIMAX_API_KEY", "wire_api": "chat"}
    },
    "constraints": {"max_input_tokens": 16000, "budget_daily_usd": 10.0, "fallback_profile": "yolo"},
    "pricing": {}
}

def _read_toml(path: str) -> DICT:
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        if tomllib:
            return tomllib.load(f)
        if tomli:
            return tomli.load(f)
        raise RuntimeError("No TOML parser available. Install tomli on Python <3.11")

def deep_merge(a: DICT, b: DICT) -> DICT:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out

def set_dotted(d: DICT, dotted: str, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def unset_dotted(d: DICT, dotted: str):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur: return
        cur = cur[p]
    if isinstance(cur, dict): cur.pop(parts[-1], None)

def _parse_scalar(s: str):
    s_strip = s.strip()
    low = s_strip.lower()
    if low in ("true","false"): return low == "true"
    if low in ("null","none"): return None
    try:
        if s_strip.isdigit() or (s_strip.startswith("-") and s_strip[1:].isdigit()):
            return int(s_strip)
        return float(s_strip)
    except ValueError:
        pass
    try:
        return json.loads(s_strip)
    except Exception:
        return s

def _env_set_list() -> list:
    s = os.environ.get("LLMC_SET","").strip()
    if not s: return []
    return [p.strip() for p in s.split(",") if p.strip()]

def apply_sets_unsets(cfg: DICT, sets: List[str], unsets: List[str]) -> DICT:
    out = copy.deepcopy(cfg)
    for item in sets or []:
        if "=" not in item: continue
        k, v = item.split("=", 1)
        set_dotted(out, k, _parse_scalar(v))
    for k in unsets or []:
        unset_dotted(out, k)
    return out

def _read_user_and_project() -> Tuple[DICT, DICT]:
    user_cfg = os.path.expanduser("~/.config/llmc/config.toml")
    proj_cfg = os.path.join(os.getcwd(), ".llmc", "config.toml")
    return _read_toml(user_cfg), _read_toml(proj_cfg)

def apply_overlays(base: DICT, overlay_paths: List[str]) -> DICT:
    cur = copy.deepcopy(base)
    for p in overlay_paths or []:
        cur = deep_merge(cur, _read_toml(p))
    return cur

def load_resolved_config(profile: str, mode: str, overlays=None, sets=None, unsets=None, strict=False) -> DICT:
    base = copy.deepcopy(DEFAULTS)
    user_cfg, proj_cfg = _read_user_and_project()
    merged = deep_merge(base, user_cfg)
    merged = deep_merge(merged, proj_cfg)
    merged = apply_overlays(merged, overlays or [])
    merged = apply_sets_unsets(merged, _env_set_list() + (sets or []), unsets or [])

    if profile not in merged.get("profiles", {}):
        raise RuntimeError(f"Unknown profile: {profile}")

    merged.setdefault("__run__", {})["mode"] = mode
    merged["defaults"]["mode"] = mode
    merged["defaults"]["profile"] = profile
    return merged

def ensure_run_snapshot(cfg: DICT, corr_id: str) -> str:
    runs_dir = os.path.join(os.getcwd(), ".llmc", "runs", corr_id)
    os.makedirs(runs_dir, exist_ok=True)
    out = os.path.join(runs_dir, "resolved-config.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return out
