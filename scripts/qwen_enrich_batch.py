#!/usr/bin/env python3
from __future__ import annotations

# ruff: noqa: I001

import argparse
import importlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

# ENTERPRISE FIX: Centralize Python cache before heavy imports.
_repo_root = Path(__file__).parent.parent.resolve()
_pycache_dir = _repo_root / ".llmc" / "pycache"
_pycache_dir.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONPYCACHEPREFIX"] = str(_pycache_dir)

# Local module wiring via dynamic imports (avoids E402 while keeping pycache prefix active).
importlib.import_module("_setup_path")

_router_mod = importlib.import_module("router")
RouterSettings = _router_mod.RouterSettings
clamp_usage_snippet = _router_mod.clamp_usage_snippet
classify_failure = _router_mod.classify_failure
choose_start_tier = _router_mod.choose_start_tier
detect_truncation = _router_mod.detect_truncation
estimate_json_nodes_and_depth = _router_mod.estimate_json_nodes_and_depth
estimate_nesting_depth = _router_mod.estimate_nesting_depth
estimate_tokens_from_text = _router_mod.estimate_tokens_from_text
expected_output_tokens = _router_mod.expected_output_tokens

_cfg_mod = importlib.import_module("tools.rag.config")
get_est_tokens_per_span = _cfg_mod.get_est_tokens_per_span
index_path_for_write = _cfg_mod.index_path_for_write

_enrich_router_mod = importlib.import_module("tools.rag.enrichment_router")
build_router_from_toml = _enrich_router_mod.build_router_from_toml
EnrichmentSliceView = _enrich_router_mod.EnrichmentSliceView

if TYPE_CHECKING:
    from tools.rag.config_enrichment import (
        EnrichmentBackendSpec as EnrichmentBackendSpecT,
        EnrichmentConfig as EnrichmentConfigT,
        filter_chain_for_tier,
        load_enrichment_config,
        select_chain,
    )
    from tools.rag.enrichment_backends import (
        BackendAdapter as BackendAdapterT,
        BackendCascade as BackendCascadeT,
    )
else:
    _cfg_enrich_mod = importlib.import_module("tools.rag.config_enrichment")
    EnrichmentBackendSpec = _cfg_enrich_mod.EnrichmentBackendSpec
    EnrichmentConfig = _cfg_enrich_mod.EnrichmentConfig
    EnrichmentConfigError = _cfg_enrich_mod.EnrichmentConfigError
    filter_chain_for_tier = _cfg_enrich_mod.filter_chain_for_tier
    load_enrichment_config = _cfg_enrich_mod.load_enrichment_config
    select_chain = _cfg_enrich_mod.select_chain

    # Router integration (SDD v2.1)
    _router_enrich_mod = importlib.import_module("tools.rag.enrichment_router")
    EnrichmentRouter = _router_enrich_mod.EnrichmentRouter
    EnrichmentSliceView = _router_enrich_mod.EnrichmentSliceView
    EnrichmentRouteDecision = _router_enrich_mod.EnrichmentRouteDecision
    build_router_from_toml = _router_enrich_mod.build_router_from_toml
_db_mod = importlib.import_module("tools.rag.database")
Database = _db_mod.Database

_backends_mod = importlib.import_module("tools.rag.enrichment_backends")
BackendAdapter = _backends_mod.BackendAdapter
BackendCascade = _backends_mod.BackendCascade
BackendError = _backends_mod.BackendError

_workers_mod = importlib.import_module("tools.rag.workers")
enrichment_plan = _workers_mod.enrichment_plan
validate_enrichment = _workers_mod.validate_enrichment

try:
    _service_mod = importlib.import_module("tools.rag.service")
    FailureTracker = getattr(_service_mod, "FailureTracker", None)
except Exception:  # pragma: no cover - failure cache optional
    FailureTracker = None


GATEWAY_DEFAULT_TIMEOUT = 300.0

_TRUTHY = {"1", "true", "yes", "on"}

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
PRESET_PATH = REPO_ROOT / "presets" / "enrich_7b_ollama.yaml"
ROUTER_POLICY_PATH = REPO_ROOT / "router" / "policy.json"
LOW_UTIL_WARN_SECONDS = 300.0
VRAM_WARN_THRESHOLD_MIB = 6800
_LOW_UTIL_STREAK_SECONDS = 0.0


@dataclass
class HealthResult:
    """Result of probing configured LLM backends."""

    checked_hosts: list[dict[str, str]]
    reachable_hosts: list[dict[str, str]]


def _normalize_ollama_url(value: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return ""
    if not trimmed.startswith(("http://", "https://")):
        trimmed = f"http://{trimmed}"
    return trimmed.rstrip("/")


def resolve_ollama_host_chain(env: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    env = env or os.environ
    hosts: list[dict[str, str]] = []

    def add_host(label: str, url: str) -> None:
        normalized = _normalize_ollama_url(url)
        if not normalized:
            return
        label = (label or "").strip() or f"host{len(hosts) + 1}"
        hosts.append({"label": label, "url": normalized})

    raw = env.get("ENRICH_OLLAMA_HOSTS", "")
    if raw:
        for chunk in raw.split(","):
            part = chunk.strip()
            if not part:
                continue
            if "=" in part:
                label, url = part.split("=", 1)
            else:
                label, url = "", part
            add_host(label, url)

    if hosts:
        return hosts

    return hosts


def health_check_ollama_hosts(
    hosts: list[dict[str, str]],
    env: Mapping[str, str],
    model_name: str,
) -> HealthResult:
    """Probe each Ollama host with a tiny request to detect obvious outages.

    Args:
        hosts: List of host dicts with 'label' and 'url' keys
        env: Environment variables
        model_name: Model to use for health check (from enrichment config)

    This is intentionally lightweight and best-effort; failures here should
    not crash the caller, but they do inform whether it is safe to proceed.
    """
    checked: list[dict[str, str]] = []
    reachable: list[dict[str, str]] = []

    timeout_env = env.get("ENRICH_HEALTHCHECK_TIMEOUT_SECONDS", "5")
    try:
        timeout_s = float(timeout_env)
    except ValueError:
        timeout_s = 5.0

    for host in hosts:
        checked.append(host)
        url = _normalize_ollama_url(host.get("url", ""))
        if not url:
            continue
        payload = json.dumps({"model": model_name, "prompt": "ping", "stream": False}).encode(
            "utf-8"
        )
        req = urllib.request.Request(
            f"{url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                # Any successful response is enough to mark this host as reachable.
                _ = resp.read(1)
        except Exception:
            continue
        reachable.append(host)

    return HealthResult(checked_hosts=checked, reachable_hosts=reachable)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError(f"PyYAML is required to load {path}; install PyYAML.")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Preset at {path} must be a mapping.")
    return data


def _detect_physical_cores() -> int:
    try:
        import psutil  # type: ignore

        cores = psutil.cpu_count(logical=False)
        if cores:
            return cores
    except Exception:
        pass

    physical_map: set[tuple[str, str]] = set()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            physical_id = ""
            core_id = ""
            for line in handle:
                if not line.strip():
                    if physical_id or core_id:
                        physical_map.add((physical_id, core_id))
                        physical_id = ""
                        core_id = ""
                    continue
                if line.startswith("physical id"):
                    physical_id = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core_id = line.split(":", 1)[1].strip()
            if physical_id or core_id:
                physical_map.add((physical_id, core_id))
    except OSError:
        pass
    cores = len(physical_map) or os.cpu_count() or 1
    return max(1, cores)


def _resolve_int(value: Any, *, default: int | None = None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in {"", "none"}:
            return default
        if stripped in {"auto", "auto_physical_cores"}:
            return _detect_physical_cores()
    return default


def _resolve_num_gpu(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in {"auto", "auto_full"}:
            return 999
        if stripped.startswith("auto_vram"):
            env_value = os.environ.get("ENRICH_NUM_GPU")
            if env_value and env_value.isdigit():
                return int(env_value)
            return 999
    return None


def _read_rss_mib() -> float | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        kib = float(parts[1])
                        return round(kib / 1024.0, 2)
    except OSError:
        return None
    return None


def _query_gpu() -> tuple[float | None, float | None]:
    cmd = [
        "nvidia-smi",
        "--id=0",
        "--query-gpu=utilization.gpu,memory.used",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None, None
    output = proc.stdout.strip()
    if not output:
        return None, None
    parts = [p.strip() for p in output.split(",")]
    if len(parts) < 2:
        return None, None
    try:
        util = float(parts[0])
        memory = float(parts[1])
    except ValueError:
        return None, None
    return util, memory


class _GpuSampler:
    def __init__(self, interval: float = 1.0) -> None:
        self.interval = max(0.2, interval)
        self.samples: list[tuple[float | None, float | None]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        if self._thread is None:
            return {"avg_util": None, "max_util": None, "avg_mem": None, "max_mem": None}
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None

        utilizations = [s[0] for s in self.samples if s[0] is not None]
        memories = [s[1] for s in self.samples if s[1] is not None]
        avg_util = statistics.fmean(utilizations) if utilizations else None
        max_util = max(utilizations) if utilizations else None
        avg_mem = statistics.fmean(memories) if memories else None
        max_mem = max(memories) if memories else None
        return {
            "avg_util": avg_util,
            "max_util": max_util,
            "avg_mem": avg_mem,
            "max_mem": max_mem,
        }

    def _run(self) -> None:
        while not self._stop.is_set():
            snapshot = _query_gpu()
            self.samples.append(snapshot)
            if self._stop.wait(self.interval):
                break


_LOCAL_HOSTNAMES = {"", "localhost", "127.0.0.1", "::1"}


def _should_sample_local_gpu(selected_backend: str, host_url: str | None) -> bool:
    if selected_backend != "ollama":
        return False
    resolved_url = host_url or os.environ.get("OLLAMA_URL")
    if not resolved_url:
        return False
    try:
        hostname = (urlparse(resolved_url).hostname or "").lower()
    except ValueError:
        return True
    if hostname in _LOCAL_HOSTNAMES:
        return True
    if hostname.endswith(".local") or hostname.endswith(".localdomain"):
        return True
    return False


def _load_enrich_presets() -> dict[str, dict[str, Any]]:
    """Legacy preset loader - now returns minimal defaults.

    Model selection is config-driven via llmc.toml enrichment chains.
    This function is retained for backward compatibility but returns empty presets.
    """
    return {"7b": {}, "14b": {}}


def _load_router_policy() -> dict[str, Any]:
    if not ROUTER_POLICY_PATH.exists():
        return {
            "default_tier": "7b",
            "fallback_tier": "14b",
            "promote_if": {"span_line_count_gte": 100, "schema_failures_gte": 2},
            "max_retries_per_span": 3,
            "log_fields": [
                "tier",
                "duration_sec",
                "schema_ok",
                "ctx",
                "batch",
                "gpu_util",
                "vram_mib",
                "rss_mib",
                "tok_s",
            ],
        }
    try:
        with ROUTER_POLICY_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to load router policy {ROUTER_POLICY_PATH}: {exc}") from exc


PRESET_CACHE = _load_enrich_presets()
POLICY_CACHE = _load_router_policy()


def env_flag(name: str, env: Mapping[str, str] | None = None) -> bool:
    env = env or os.environ
    raw = env.get(name, "").strip().lower()
    return raw in _TRUTHY


def azure_env_available(env: Mapping[str, str] | None = None) -> bool:
    env = env or os.environ
    required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT"]
    return all(env.get(key) for key in required)


def infer_effective_tier(meta: dict[str, object], fallback: str) -> str:
    """Derive the tier label from backend/meta instead of router guesswork."""

    backend = str(meta.get("backend") or "").lower()
    model = str(meta.get("model") or "").lower()

    if backend == "gateway":
        return "nano"

    if "nano" in model:
        return "nano"

    tier_map = (
        ("14b", "14b"),
        ("13b", "14b"),
        ("12b", "14b"),
        ("11b", "14b"),
        ("10b", "14b"),
        ("9b", "14b"),
        ("8b", "14b"),
        ("7b", "7b"),
        ("6.7b", "7b"),
        ("6b", "7b"),
        ("5b", "7b"),
        ("4b", "7b"),
        ("3b", "7b"),
    )

    for keyword, tier in tier_map:
        if keyword in model:
            return tier

    if backend:
        return backend

    return fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch enrichment runner using local Qwen via codex_wrap.sh."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repository root to enrich (default: current working directory).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of spans to request per loop iteration (default: 5).",
    )
    parser.add_argument(
        "--max-spans",
        type=int,
        default=0,
        help="Maximum number of spans to enrich (0 = no limit).",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Metrics JSONL path (default: <repo>/logs/enrichment_metrics.jsonl).",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Model identifier to record with enrichments.",
    )
    parser.add_argument(
        "--schema-version",
        default="enrichment.v1",
        dest="schema_version",
        help="Schema version tag for stored enrichments.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Optional delay (seconds) between spans.",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=0,
        help="Skip spans whose source file changed within the last N seconds (default: 0).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of times to retry a span when the local model returns no response (default: 3).",
    )
    parser.add_argument(
        "--retry-wait",
        type=float,
        default=2.0,
        help="Seconds to wait between retries when the local model fails to respond.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Iterate and report prompts without calling the LLM.",
    )
    parser.add_argument(
        "--dry-run-plan",
        action="store_true",
        help="Show planned spans to enrich and exit without calling the LLM or writing enrichments.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print prompts and responses for debugging.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "ollama", "gateway"],
        default="auto",
        help="LLM backend to use (default: auto-detect based on environment).",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Shortcut for --backend gateway (prefer API/gateway backend).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Shortcut for --backend ollama (force local Ollama backend).",
    )
    parser.add_argument(
        "--gateway-path",
        type=Path,
        default=REPO_ROOT / "scripts" / "llm_gateway.js",
        help="Path to llm_gateway.js for API-backed calls.",
    )
    parser.add_argument(
        "--gateway-timeout",
        type=float,
        default=300.0,
        help="Timeout (seconds) for gateway-backed completions (default: 300).",
    )
    parser.add_argument(
        "--fallback-model",
        default=os.environ.get("RAG_FALLBACK_MODEL", "qwen2.5:14b-instruct-q4_K_M"),
        help="Alternate Ollama model to retry on failure (blank to skip).",
    )
    parser.add_argument(
        "--no-gateway-fallback",
        action="store_true",
        help="Do not retry via gateway after local fallbacks.",
    )
    parser.add_argument(
        "--router",
        choices=["on", "off"],
        default=os.environ.get("ROUTER_ENABLED", "on"),
        help="Enable or disable automatic tier routing (default: on).",
    )
    parser.add_argument(
        "--enforce-latin1",
        action="store_true",
        help="Reject enrichments containing non-Latin-1 characters.",
    )
    parser.add_argument(
        "--start-tier",
        choices=["auto", "7b", "14b", "nano"],
        default=os.environ.get("ROUTER_DEFAULT_TIER", "auto"),
        help="Override starting tier (auto respects routing policy).",
    )
    parser.add_argument(
        "--max-tokens-headroom",
        type=int,
        default=int(os.environ.get("ROUTER_MAX_TOKENS_HEADROOM", "4000")),
        help="Reserved headroom below context limit when routing (default: 4000).",
    )
    parser.add_argument(
        "--chain-name",
        type=str,
        default=None,
        help="Optional enrichment chain name from llmc.toml [enrichment.chain].",
    )
    parser.add_argument(
        "--chain-config",
        type=Path,
        default=None,
        help="Optional path to a TOML containing [enrichment] config (overrides repo llmc.toml).",
    )
    return parser.parse_args()


def ensure_repo(repo_root: Path) -> Path:
    repo_root = repo_root.resolve()
    if not (repo_root / ".git").exists():
        raise SystemExit(f"{repo_root} does not look like a git repo (missing .git/).")
    return repo_root


def build_prompt(item: dict[str, Any], repo_root: Path) -> str:
    path = item["path"]
    line_start, line_end = item["lines"]
    snippet = item.get("code_snippet", "")

    prompt = f"""Return ONLY ONE VALID JSON OBJECT in ENGLISH.
No markdown, no comments, no extra text.

Output example (structure and keys are FIXED):
{{"summary_120w":"...","inputs":["..."],"outputs":["..."],
"side_effects":["..."],"pitfalls":["..."],
"usage_snippet":"...","evidence":[{{"field":"summary_120w","lines":[{line_start},{line_end}]}}]}}

Rules:
- summary_120w: <=120 English words describing what the code does.
- inputs/outputs/side_effects/pitfalls: lists of short phrases; use [] if none.
- usage_snippet: 1–5 line usage example, or "" if unclear.
- evidence: list of objects:
  - "field" is one of:
    "summary_120w","inputs","outputs","side_effects","pitfalls","usage_snippet"
  - "lines" MUST be [{line_start},{line_end}] for every entry.
- Do NOT add or rename keys.
- Use double quotes, no trailing commas.

Code to analyze:
{path} L{line_start}-{line_end}:
{snippet}

JSON RESPONSE LATIN-1 CHARACTERS ONLY:"""
    return prompt


def call_via_ollama(
    prompt: str,
    repo_root: Path,
    verbose: bool = False,
    retries: int = 3,
    retry_wait: float = 2.0,
    poll_wait: float = 1.5,
    model_override: str | None = None,
    options: dict[str, Any] | None = None,
    keep_alive: str | float | int | None = None,
    base_url: str | None = None,
    host_label: str | None = None,
) -> tuple[str, dict[str, object]]:
    base_url = (base_url or os.environ.get("OLLAMA_URL", "")).rstrip("/")
    if not base_url:
        raise ValueError("Ollama base URL not configured. Set OLLAMA_URL or check chain config.")

    model_name = model_override or os.environ.get("OLLAMA_MODEL", "")
    if not model_name:
        raise ValueError("Ollama model not configured. Set OLLAMA_MODEL or check chain config.")

    payload_dict: dict[str, Any] = {"model": model_name, "prompt": prompt, "stream": False}
    if options:
        payload_dict["options"] = options
    if keep_alive is not None:
        payload_dict["keep_alive"] = keep_alive
    payload = json.dumps(payload_dict).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    # Logic to wait for 'runner_active' removed as it blocks on loaded models.
    # Ollama handles concurrency internally.

    attempt = 0
    last_error: Exception | None = None
    while attempt < max(1, retries):
        attempt += 1
        try:
            req = urllib.request.Request(
                f"{base_url}/api/generate",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            if attempt < max(1, retries):
                time.sleep(max(0.0, retry_wait))
            continue

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            segments = [line for line in body.splitlines() if line.strip()]
            combined = ""
            last_data = None
            for seg in segments:
                obj = json.loads(seg)
                last_data = obj
                if isinstance(obj.get("response"), str):
                    combined += obj["response"]
            if last_data and combined:
                meta = {
                    "backend": "ollama",
                    "model": model_name,
                    "finish_reason": last_data.get("done_reason"),
                    "eval_count": last_data.get("eval_count"),
                    "options": payload_dict.get("options"),
                    "base_url": base_url,
                    "host": host_label or base_url,
                }
                if keep_alive is not None:
                    meta["keep_alive"] = keep_alive
                return combined, meta
            last_error = ValueError("Failed to parse Ollama response")
        else:
            response_text = data.get("response", "")
            if isinstance(response_text, str) and response_text.strip():
                meta = {
                    "backend": "ollama",
                    "model": model_name,
                    "finish_reason": data.get("done_reason"),
                    "eval_count": data.get("eval_count"),
                    "options": payload_dict.get("options"),
                    "base_url": base_url,
                    "host": host_label or base_url,
                }
                if keep_alive is not None:
                    meta["keep_alive"] = keep_alive
                return response_text, meta
            last_error = ValueError("No response from Ollama")

        if attempt < max(1, retries):
            time.sleep(max(0.0, retry_wait))
    assert last_error is not None
    raise last_error


def call_via_gateway(
    prompt: str,
    repo_root: Path,
    gateway_path: Path,
    timeout: float = GATEWAY_DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> tuple[str, dict[str, object]]:
    if not gateway_path.exists():
        raise FileNotFoundError(f"llm gateway not found at {gateway_path}")

    env = os.environ.copy()
    # Ensure LLM is not disabled when delegating to the gateway.
    env.setdefault("LLM_DISABLED", "false")
    env.setdefault("NEXT_PUBLIC_LLM_DISABLED", "false")
    env.setdefault("LLM_GATEWAY_DISABLE_RAG", "1")

    args = ["node", str(gateway_path), "--api"]
    if verbose:
        args.append("--debug")

    proc = subprocess.run(
        args,
        input=prompt,
        text=True,
        cwd=str(repo_root),
        env=env,
        timeout=timeout,
        capture_output=True,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"llm gateway failed (exit {proc.returncode}): {proc.stderr.strip() or 'no stderr'}"
        )
    output = proc.stdout.strip()
    if not output:
        raise RuntimeError("llm gateway returned empty output")
    meta: dict[str, object] = {
        "backend": "gateway",
    }
    return output, meta


def call_qwen(
    prompt: str,
    repo_root: Path,
    *,
    backend: str = "auto",
    verbose: bool = False,
    retries: int = 3,
    retry_wait: float = 2.0,
    poll_wait: float = 1.5,
    gateway_path: Path | None = None,
    gateway_timeout: float = GATEWAY_DEFAULT_TIMEOUT,
    model_override: str | None = None,
    ollama_options: dict[str, Any] | None = None,
    keep_alive: str | float | int | None = None,
    ollama_base_url: str | None = None,
    ollama_host_label: str | None = None,
) -> tuple[str, dict[str, object]]:
    backend = backend or "auto"
    backend = backend.lower()
    env = os.environ
    prefer_gateway = backend == "gateway" or (
        backend == "auto"
        and (
            azure_env_available(env)
            or env_flag("LLM_GATEWAY_DISABLE_LOCAL", env)
            or env_flag("LLM_GATEWAY_FORCE_GATEWAY", env)
        )
    )

    errors: list[Exception] = []
    if prefer_gateway:
        if gateway_path is None:
            gateway_path = REPO_ROOT / "scripts" / "llm_gateway.js"
        try:
            output, meta = call_via_gateway(
                prompt,
                repo_root,
                gateway_path=gateway_path,
                timeout=gateway_timeout,
                verbose=verbose,
            )
            backend_label = meta.get("backend", "gateway")
            model_label = meta.get("model") or (
                env.get("AZURE_OPENAI_DEPLOYMENT")
                if azure_env_available(env)
                else env.get("GEMINI_MODEL", "gemini")
            )
            meta.setdefault("backend", backend_label)
            meta.setdefault("model", model_label)
            return output, meta
        except Exception as exc:
            errors.append(exc)
            if backend == "gateway":
                raise
            # Fall through to ollama attempt.

    try:
        model_label = model_override or os.environ.get("OLLAMA_MODEL")
        if not model_label:
            raise RuntimeError(
                "No model specified. Please set 'model' in llmc.toml chain config or OLLAMA_MODEL env var."
            )
        output, meta = call_via_ollama(
            prompt,
            repo_root,
            verbose=verbose,
            retries=retries,
            retry_wait=retry_wait,
            poll_wait=poll_wait,
            model_override=model_override,
            options=ollama_options,
            keep_alive=keep_alive,
            base_url=ollama_base_url,
            host_label=ollama_host_label,
        )
        meta.setdefault("backend", "ollama")
        meta.setdefault("model", model_label)
        if ollama_host_label or ollama_base_url:
            meta.setdefault("host", ollama_host_label or ollama_base_url)
        return output, meta
    except Exception as exc:
        errors.append(exc)
        if errors:
            msgs = "; ".join(str(e) for e in errors)
            raise RuntimeError(msgs) from exc
        raise


@dataclass
class _AdapterConfigShim:
    """Minimal config stand-in for backend adapters.

    This lets adapters always expose a ``.config`` object with the fields
    we care about (name, provider, model, tier, url, options, keep_alive)
    without importing the real enrichment config schema into this module.
    """

    name: str
    provider: str
    model: str | None = None
    tier: str | None = None
    url: str | None = None
    options: dict[str, Any] | None = None
    keep_alive: str | float | int | None = None


class _OllamaBackendAdapter:
    """BackendAdapter for Ollama backends.

    This adapter is responsible for:

    - Merging preset options from ``PRESET_CACHE`` with any per-backend
      overrides from configuration.
    - Invoking :func:`call_qwen` with ``backend="ollama"``.
    - Running :func:`parse_and_validate` on the raw output.
    - Mapping any failures to :class:`BackendError`.
    """

    def __init__(
        self,
        *,
        config: object | None,
        repo_root: Path,
        args: argparse.Namespace,
        host_url: str,
        host_label: str | None,
        tier_preset: dict[str, Any],
        tier_for_attempt: str,
    ) -> None:
        self._repo_root = repo_root
        self._args = args
        self._host_url = host_url
        self._host_label = host_label or host_url
        self._tier_for_attempt = tier_for_attempt
        # Shallow copy so downstream tweaks never mutate PRESET_CACHE.
        self._tier_preset: dict[str, Any] = dict(tier_preset or {})
        if config is None:
            self._config: object = _AdapterConfigShim(
                name=f"ollama-{tier_for_attempt}",
                provider="ollama",
                model=self._tier_preset.get("model"),
                tier=tier_for_attempt,
                url=host_url,
                options=self._tier_preset.get("options"),
                keep_alive=self._tier_preset.get("keep_alive"),
            )
        else:
            self._config = config

    @property
    def config(self) -> object:
        return self._config

    def describe_host(self) -> str | None:
        return self._host_label or self._host_url

    def _resolve_effective_params(
        self,
    ) -> tuple[dict[str, Any] | None, str | float | int | None, str | None]:
        """Merge preset + config-specific overrides.

        Returns ``(options, keep_alive, model_override)``.
        """

        options = self._tier_preset.get("options")
        keep_alive = self._tier_preset.get("keep_alive")
        model_override = self._tier_preset.get("model")

        cfg = self._config
        cfg_options = getattr(cfg, "options", None)
        if cfg_options:
            try:
                # Take a copy so we never mutate the underlying config.
                options = dict(cfg_options)
            except TypeError:
                options = cfg_options  # Fall back to value as-is.

        cfg_keep_alive = getattr(cfg, "keep_alive", None)
        if cfg_keep_alive is not None:
            keep_alive = cfg_keep_alive

        cfg_model = getattr(cfg, "model", None)
        if isinstance(cfg_model, str) and cfg_model:
            model_override = cfg_model

        return options, keep_alive, model_override

    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute a single Ollama enrichment attempt."""

        options, keep_alive, model_override = self._resolve_effective_params()

        try:
            stdout, meta = call_qwen(
                prompt,
                self._repo_root,
                backend="ollama",
                verbose=self._args.verbose,
                retries=self._args.retries,
                retry_wait=self._args.retry_wait,
                poll_wait=1.5,
                gateway_path=self._args.gateway_path,
                gateway_timeout=self._args.gateway_timeout,
                model_override=model_override,
                ollama_options=options,
                keep_alive=keep_alive,
                ollama_base_url=self._host_url,
                ollama_host_label=self._host_label,
            )
        except RuntimeError as exc:
            raise BackendError(
                f"Ollama runtime failure on {self.describe_host()}: {exc}",
                failure_type="runtime",
            ) from exc

        result, failure = parse_and_validate(
            stdout, item, meta, enforce_latin1=self._args.enforce_latin1
        )
        if result is not None:
            # Ensure meta has useful defaults for downstream metrics.
            if "model" not in meta and isinstance(model_override, str):
                meta["model"] = model_override
            meta.setdefault("backend", "ollama")
            meta.setdefault("host", self.describe_host())
            meta.setdefault("host_url", self._host_url)
            # Config-driven metadata (Phase 5)
            cfg = self._config
            backend_name = getattr(cfg, "name", None)
            chain_name = getattr(cfg, "chain", None)
            if backend_name and "backend_name" not in meta:
                meta["backend_name"] = backend_name
            if chain_name and "chain_name" not in meta:
                meta["chain_name"] = chain_name
            return result, meta

        # Any parse/validation/truncation failure is mapped to BackendError.
        if failure is None:
            kind = "runtime"
            detail: object = RuntimeError("unknown failure")
        else:
            kind, detail, payload = failure
        raise BackendError(
            f"{kind} failure on Ollama backend {self.describe_host()}: {detail}",
            failure_type=str(kind),
            failure=failure,
        )


class _GatewayBackendAdapter:
    """BackendAdapter for gateway / Gemini backends.

    This adapter wraps :func:`call_qwen` with ``backend="gateway"`` and
    optionally overrides the ``GEMINI_MODEL`` environment variable while
    the call is in flight. This keeps the actual gateway integration logic
    localized to :func:`call_qwen`.
    """

    def __init__(
        self,
        *,
        config: object | None,
        repo_root: Path,
        args: argparse.Namespace,
    ) -> None:
        self._repo_root = repo_root
        self._args = args
        self._config = config or _AdapterConfigShim(
            name="gateway",
            provider="gateway",
            model=None,
            tier=None,
            url="gateway",
        )

    @property
    def config(self) -> object:
        return self._config

    def describe_host(self) -> str | None:
        return "gateway"

    def _resolve_model(self) -> str | None:
        cfg_model = getattr(self._config, "model", None)
        if isinstance(cfg_model, str) and cfg_model:
            return cfg_model
        return None

    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute a single gateway enrichment attempt."""

        gateway_model_prev: str | None = None
        gateway_model_env_changed = False
        cfg_model = self._resolve_model()
        if cfg_model:
            gateway_model_prev = os.environ.get("GEMINI_MODEL")
            os.environ["GEMINI_MODEL"] = cfg_model
            gateway_model_env_changed = True

        try:
            try:
                stdout, meta = call_qwen(
                    prompt,
                    self._repo_root,
                    backend="gateway",
                    verbose=self._args.verbose,
                    retries=self._args.retries,
                    retry_wait=self._args.retry_wait,
                    poll_wait=1.5,
                    gateway_path=self._args.gateway_path,
                    gateway_timeout=self._args.gateway_timeout,
                    model_override=None,
                    ollama_options=None,
                    keep_alive=None,
                    ollama_base_url=None,
                    ollama_host_label=None,
                )
            except RuntimeError as exc:
                raise BackendError(
                    f"Gateway runtime failure: {exc}",
                    failure_type="runtime",
                ) from exc

            result, failure = parse_and_validate(
                stdout, item, meta, enforce_latin1=self._args.enforce_latin1
            )
            if result is not None:
                if "model" not in meta and isinstance(cfg_model, str):
                    meta["model"] = cfg_model
                meta.setdefault("backend", "gateway")
                # Config-driven metadata (Phase 5)
                cfg = self._config
                backend_name = getattr(cfg, "name", None)
                chain_name = getattr(cfg, "chain", None)
                if backend_name and "backend_name" not in meta:
                    meta["backend_name"] = backend_name
                if chain_name and "chain_name" not in meta:
                    meta["chain_name"] = chain_name
                return result, meta

            if failure is None:
                kind = "runtime"
                detail: object = RuntimeError("unknown failure")
            else:
                kind, detail, payload = failure
            raise BackendError(
                f"{kind} failure on gateway backend: {detail}",
                failure_type=str(kind),
                failure=failure,
            )
        finally:
            if gateway_model_env_changed:
                if gateway_model_prev is None:
                    os.environ.pop("GEMINI_MODEL", None)
                else:
                    os.environ["GEMINI_MODEL"] = gateway_model_prev


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not locate JSON object in LLM output.")
    payload = text[start : end + 1]
    return json.loads(payload)


ALLOWED_FIELDS = {
    "summary_120w",
    "inputs",
    "outputs",
    "side_effects",
    "pitfalls",
    "usage_snippet",
}


def normalize_evidence(
    result: dict, line_start: int, line_end: int, allowed_fields: set[str] = ALLOWED_FIELDS
) -> None:
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    # Drop entries with unexpected shapes or field values we do not track.
    filtered: list[dict] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        lines = item.get("lines")
        if field not in allowed_fields:
            continue
        if (
            not isinstance(lines, list)
            or len(lines) != 2
            or not all(isinstance(v, int) for v in lines)
        ):
            continue
        filtered.append({"field": field, "lines": lines})
    evidence = filtered

    def has_field(field: str) -> bool:
        return any(entry["field"] == field for entry in evidence)

    for field in ["summary_120w", "inputs", "outputs", "side_effects", "pitfalls", "usage_snippet"]:
        value = result.get(field)
        if field == "usage_snippet":
            if not isinstance(value, str) or not value.strip():
                continue
        elif not value:
            continue
        if not has_field(field):
            evidence.append({"field": field, "lines": [line_start, line_end]})

    result["evidence"] = evidence


def _as_list_of_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                trimmed = entry.strip()
                if trimmed:
                    items.append(trimmed)
        return items
    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else []
    return []


def normalize_schema_fields(result: dict) -> None:
    array_fields = ["inputs", "outputs", "side_effects", "pitfalls", "tags"]
    for field in array_fields:
        result[field] = _as_list_of_strings(result.get(field))

    text_fields = ["summary_120w"]
    for field in text_fields:
        value = result.get(field)
        if value is None:
            result[field] = ""
        elif not isinstance(value, str):
            result[field] = str(value)
        else:
            result[field] = value.strip()

    snippet = result.get("usage_snippet")
    if snippet is None:
        result["usage_snippet"] = None
    elif not isinstance(snippet, str):
        result["usage_snippet"] = str(snippet)
    else:
        result["usage_snippet"] = snippet.strip() or None

    if not isinstance(result.get("evidence"), list):
        result["evidence"] = []


def parse_and_validate(
    raw: str,
    item: dict[str, Any],
    meta: dict[str, object],
    enforce_latin1: bool = False,
) -> tuple[dict[str, Any] | None, tuple[str, object, object] | None]:
    try:
        result = extract_json(raw)
    except ValueError as exc:
        finish_reason = str(meta.get("finish_reason") or "")
        eval_count = meta.get("eval_count")
        tokens_used = None
        if isinstance(eval_count, int):
            tokens_used = eval_count
        if detect_truncation(raw, tokens_used, finish_reason):
            return None, ("truncation", exc, raw)
        return None, ("parse", exc, raw)

    normalize_schema_fields(result)
    clamp_usage_snippet(result, max_lines=12)
    normalize_evidence(result, item["lines"][0], item["lines"][1])
    ok, errors = validate_enrichment(
        result, item["lines"][0], item["lines"][1], enforce_latin1=enforce_latin1
    )
    if not ok:
        return None, ("validation", errors, result)

    return result, None


def handle_failure(
    repo_root: Path, item: dict[str, Any], failure: tuple[str, object, object]
) -> None:
    kind, detail, payload = failure
    if kind in {"parse", "truncation"}:
        raw = payload if isinstance(payload, str) else ""
        log_dir = repo_root / "logs" / "failed_enrichments"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        log_path = log_dir / f"{item['span_hash']}_{timestamp}.json"
        try:
            log_path.write_text(raw, encoding="utf-8")
        except OSError:
            pass
        message = "JSON parsing failed" if kind == "parse" else "Model output truncated"
        print(
            f"{message} for {item['span_hash']} ({item['path']}:{item['lines']}): {detail}. Raw output saved to {log_path}",
            file=sys.stderr,
        )
    elif kind == "validation":
        print(
            f"Validation failed for {item['span_hash']} ({item['path']}:{item['lines']}): {detail}",
            file=sys.stderr,
        )
    else:
        print(
            f"Enrichment failed for {item['span_hash']} ({item['path']}:{item['lines']}): {detail}",
            file=sys.stderr,
        )


def append_metrics(log_path: Path, metrics: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False)
        handle.write("\n")


def append_ledger_record(log_path: Path, record: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")


def _build_cascade_for_attempt(
    *,
    backend: str,
    tier_for_attempt: str,
    repo_root: Path,
    args: argparse.Namespace,
    ollama_host_chain: Sequence[Mapping[str, object]],
    current_host_idx: int,
    host_chain_count: int,
    enrichment_config: EnrichmentConfigT | None = None,
    selected_chain: Sequence[EnrichmentBackendSpecT] | None = None,
    backend_specs: Sequence[EnrichmentBackendSpecT] | None = None,
) -> tuple[BackendCascadeT, str, dict[str, Any], str | None, str | None, str, str | None]:
    """Build a BackendCascade and preset metadata for a single attempt.

    This mirrors the existing tier/back-end selection logic in ``main`` but
    can optionally use a config-driven enrichment chain or router-provided specs.
    """

    backend_choice = "gateway" if tier_for_attempt == "nano" else "ollama"
    selected_backend = backend_choice if backend == "auto" else backend
    preset_key = "14b" if tier_for_attempt == "14b" else "7b"
    tier_preset = PRESET_CACHE.get(preset_key, PRESET_CACHE["7b"])

    adapters: list[BackendAdapterT] = []
    host_label: str | None = None
    host_url: str | None = None
    chain_name_used: str | None = None

    # Router path: use explicit backend_specs if provided.
    # Or Config-driven path: build adapters from EnrichmentConfig if available.
    specs_to_use = None
    if backend_specs is not None:
        specs_to_use = list(backend_specs)
    elif enrichment_config is not None and selected_chain:
        try:
            specs_to_use = filter_chain_for_tier(list(selected_chain), tier_for_attempt)
        except Exception:
            specs_to_use = []

    if specs_to_use:
        if specs_to_use:
            chain_name_used = specs_to_use[0].chain
            for spec in specs_to_use:
                provider = spec.provider
                if provider == "ollama":
                    url = spec.url or ""
                    label = spec.name or url
                    adapters.append(
                        _OllamaBackendAdapter(
                            config=spec,
                            repo_root=repo_root,
                            args=args,
                            host_url=url,
                            host_label=label,
                            tier_preset=tier_preset,
                            tier_for_attempt=tier_for_attempt,
                        )
                    )
                    if host_url is None:
                        host_url = url
                        host_label = label
                elif provider in {"gateway", "gemini"}:
                    adapters.append(
                        _GatewayBackendAdapter(
                            config=spec,
                            repo_root=repo_root,
                            args=args,
                        )
                    )
                else:
                    # Unknown providers should have been rejected by config loader.
                    continue

            if adapters:
                if isinstance(adapters[0], _GatewayBackendAdapter):
                    selected_backend = "gateway"
                else:
                    selected_backend = "ollama"
                cascade = BackendCascade(backends=adapters)
                return (
                    cascade,
                    preset_key,
                    tier_preset,
                    host_label,
                    host_url,
                    selected_backend,
                    chain_name_used,
                )

    # Legacy path: mirror existing tier/backend + host-chain behaviour.
    if selected_backend == "ollama":
        host_entry: Mapping[str, object] | None = None
        if ollama_host_chain:
            host_entry = ollama_host_chain[min(current_host_idx, host_chain_count - 1)]
            host_label = str(host_entry.get("label") or "")
            host_url = str(host_entry.get("url") or "")
        adapters.append(
            _OllamaBackendAdapter(
                config=None,
                repo_root=repo_root,
                args=args,
                host_url=host_url or "",
                host_label=host_label,
                tier_preset=tier_preset,
                tier_for_attempt=tier_for_attempt,
            )
        )
    elif selected_backend in {"gateway", "nano"}:
        adapters.append(
            _GatewayBackendAdapter(
                config=None,
                repo_root=repo_root,
                args=args,
            )
        )
    else:
        # Fallback to Ollama semantics for unknown backends so behaviour
        # degrades gracefully even if a future CLI/backend value is passed.
        adapters.append(
            _OllamaBackendAdapter(
                config=None,
                repo_root=repo_root,
                args=args,
                host_url="",
                host_label=None,
                tier_preset=tier_preset,
                tier_for_attempt=tier_for_attempt,
            )
        )
        selected_backend = "ollama"

    cascade = BackendCascade(backends=adapters)
    return cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name_used


def main() -> int:
    args = parse_args()
    repo_root = ensure_repo(args.repo)

    force_legacy = env_flag("LLMC_ENRICH_FORCE_LEGACY")
    strict_config = env_flag("LLMC_ENRICH_STRICT_CONFIG")
    summary_json_path = os.environ.get("LLMC_ENRICH_SUMMARY_JSON")
    enrichment_config: EnrichmentConfigT | None = None
    selected_chain: Sequence[EnrichmentBackendSpecT] | None = None
    enrichment_router = None  # Router integration (SDD v2.1)
    if not force_legacy:
        try:
            enrichment_config = load_enrichment_config(
                repo_root=repo_root,
                toml_path=args.chain_config,
            )
            # Build router for future per-span routing (SDD v2.1 Phase 2+)
            try:
                enrichment_router = build_router_from_toml(
                    repo_root=repo_root,
                    env=os.environ,
                    toml_path=args.chain_config,
                )
                if args.verbose and enrichment_router.enable_routing:
                    print(
                        f"[enrichment] router enabled with {len(enrichment_router.routes)} routes",
                        file=sys.stderr,
                    )
            except Exception as router_exc:
                if args.verbose:
                    print(
                        f"[enrichment] router init failed: {router_exc}; using direct chain selection",
                        file=sys.stderr,
                    )
                enrichment_router = None

            selected_chain = select_chain(enrichment_config, args.chain_name)
        except EnrichmentConfigError as exc:  # type: ignore[name-defined]
            print(
                f"[enrichment] config error: {exc}",
                file=sys.stderr,
            )
            if strict_config:
                return 2
            enrichment_config = None
            selected_chain = None
            if args.verbose:
                print(
                    "[enrichment] falling back to presets (legacy mode).",
                    file=sys.stderr,
                )
    else:
        if args.verbose:
            print(
                "[enrichment] LLMC_ENRICH_FORCE_LEGACY is set – skipping llmc.toml config.",
                file=sys.stderr,
            )
    if enrichment_config is not None and not selected_chain:
        chain_name = args.chain_name or getattr(enrichment_config, "default_chain", "<default>")
        print(
            f"[enrichment] config has no enabled backends for chain {chain_name!r}.",
            file=sys.stderr,
        )
        if strict_config:
            return 2
        if args.verbose:
            print(
                "[enrichment] falling back to presets (legacy mode).",
                file=sys.stderr,
            )
        enrichment_config = None
        selected_chain = None

    # Config-driven CLI defaults (Phase 3):
    # If the user did not override certain args on the CLI (they are still at
    # their argparse defaults), let the enrichment config fill them in.
    if enrichment_config is not None:
        try:
            # batch_size defaults to 5 in argparse; treat that as 'no override'.
            if getattr(args, "batch_size", None) == 5:
                cfg_batch = getattr(enrichment_config, "batch_size", None)
                if isinstance(cfg_batch, int) and cfg_batch > 0:
                    if args.verbose:
                        print(
                            f"[enrichment] applying config batch_size={cfg_batch} (from llmc.toml)",
                            file=sys.stderr,
                        )
                    args.batch_size = cfg_batch

            # cooldown defaults to 0 seconds; only override when still at default.
            if getattr(args, "cooldown", None) == 0:
                cfg_cooldown = getattr(enrichment_config, "cooldown_seconds", None)
                if isinstance(cfg_cooldown, int) and cfg_cooldown >= 0:
                    if args.verbose and cfg_cooldown:
                        print(
                            f"[enrichment] applying config cooldown_seconds={cfg_cooldown} (from llmc.toml)",
                            file=sys.stderr,
                        )
                    args.cooldown = cfg_cooldown

            # retries default to 3; again, treat that as 'no override'.
            if getattr(args, "retries", None) == 3:
                cfg_retries = getattr(enrichment_config, "max_retries_per_span", None)
                if isinstance(cfg_retries, int) and cfg_retries > 0:
                    if args.verbose:
                        print(
                            f"[enrichment] applying config max_retries_per_span={cfg_retries} (from llmc.toml)",
                            file=sys.stderr,
                        )
                    args.retries = cfg_retries

            # enforce_latin1 defaults to False; override if config says True
            if not getattr(args, "enforce_latin1", False):
                cfg_latin1 = getattr(enrichment_config, "enforce_latin1_enrichment", False)
                if cfg_latin1:
                    if args.verbose:
                        print(
                            "[enrichment] applying config enforce_latin1=True (from llmc.toml)",
                            file=sys.stderr,
                        )
                    args.enforce_latin1 = True
        except Exception:
            # Config is best-effort; if anything goes wrong, keep argparse values.
            if args.verbose:
                print(
                    "[enrichment] failed to apply config-driven CLI defaults; keeping argparse values.",
                    file=sys.stderr,
                )

    pipeline_mode = "config" if enrichment_config is not None and selected_chain else "legacy"
    effective_chain: str | None = None
    if enrichment_config is not None:
        try:
            effective_chain = args.chain_name or getattr(enrichment_config, "default_chain", None)
        except Exception:
            effective_chain = args.chain_name

    backend = args.backend
    if args.api:
        backend = "gateway"
    elif args.local:
        backend = "ollama"

    if args.verbose:
        print(f"Backend selection: {backend}", file=sys.stderr)

    if enrichment_config is not None and selected_chain and getattr(args, "verbose", False):
        effective_chain = args.chain_name or getattr(
            enrichment_config, "default_chain", "<default>"
        )
        print(
            f"[enrichment] using config-driven pipeline for chain {effective_chain!r}.",
            file=sys.stderr,
        )
    if args.cooldown:
        print(f"Cooldown: skipping spans modified within last {args.cooldown}s", file=sys.stderr)
    log_path = args.log or (repo_root / "logs" / "enrichment_metrics.jsonl")

    router_enabled = (args.router or "on").lower() != "off"
    policy_settings = POLICY_CACHE.copy()
    policy_default_tier = str(policy_settings.get("default_tier", "7b")).lower()
    policy_fallback_tier = str(policy_settings.get("fallback_tier", "14b")).lower()
    promote_cfg = policy_settings.get("promote_if", {}) or {}
    policy_line_threshold = int(promote_cfg.get("span_line_count_gte", 100) or 100)
    policy_schema_threshold = int(promote_cfg.get("schema_failures_gte", 2) or 2)
    policy_max_retries = int(
        policy_settings.get("max_retries_per_span", args.retries) or args.retries
    )
    policy_log_fields = list(policy_settings.get("log_fields", []))
    settings = RouterSettings(headroom=args.max_tokens_headroom)
    ledger_path = repo_root / "logs" / "run_ledger.log"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ollama_host_chain = resolve_ollama_host_chain()
    health_check_model: str | None = None

    # Merge hosts from config into the health check list
    if enrichment_config:
        existing_urls = {h["url"] for h in ollama_host_chain}
        for chain_backends in enrichment_config.chains.values():
            for backend_spec in chain_backends:
                if backend_spec.enabled and backend_spec.provider == "ollama" and backend_spec.url:
                    if backend_spec.model and not health_check_model:
                        health_check_model = backend_spec.model
                    normalized = _normalize_ollama_url(backend_spec.url)
                    if normalized and normalized not in existing_urls:
                        ollama_host_chain.append(
                            {"label": backend_spec.name or "config-host", "url": normalized}
                        )
                        existing_urls.add(normalized)
    host_chain_count = max(1, len(ollama_host_chain))

    # Optional pre-flight health check for backends to fail fast when LLMs are down.
    env = os.environ
    if env.get("ENRICH_HEALTHCHECK_ENABLED", "true").strip().lower() in _TRUTHY:
        if not health_check_model:
            print(
                "[rag-enrich] WARNING: No model found in enrichment config for health check. "
                "Skipping health check. Ensure llmc.toml has at least one enabled enrichment chain with a model.",
                file=sys.stderr,
                flush=True,
            )
        elif ollama_host_chain:
            health = health_check_ollama_hosts(
                ollama_host_chain, env, model_name=health_check_model
            )
            if not health.reachable_hosts:
                checked_labels = [h.get("label") or h.get("url") for h in health.checked_hosts]
                print(
                    f"[rag-enrich] ERROR: No reachable Ollama hosts for repo {repo_root}. "
                    f"Checked: {checked_labels}",
                    file=sys.stderr,
                    flush=True,
                )
                return 2
            else:
                reachable_labels = [h.get("label") or h.get("url") for h in health.reachable_hosts]
                print(
                    f"[rag-enrich] Healthcheck OK: reachable Ollama hosts = {reachable_labels}",
                    flush=True,
                )

    db_file = index_path_for_write(repo_root)
    db = Database(db_file)
    failure_tracker = None
    repo_key = str(repo_root)
    if FailureTracker is not None:
        try:
            failure_tracker = FailureTracker()
        except Exception:
            failure_tracker = None
    processed = 0
    attempted = 0
    failed = 0
    try:
        while True:
            remaining = args.max_spans - processed if args.max_spans else None
            if remaining is not None and remaining <= 0:
                break
            this_batch = args.batch_size if remaining is None else min(args.batch_size, remaining)
            plan = enrichment_plan(db, repo_root, limit=this_batch, cooldown_seconds=args.cooldown)
            if failure_tracker is not None and plan:
                original_len = len(plan)
                plan = [
                    item
                    for item in plan
                    if not failure_tracker.is_failed(item["span_hash"], repo_key)
                ]
                if args.verbose and original_len and not plan:
                    print(
                        "[enrichment] all spans in this batch skipped due to failure limits.",
                        file=sys.stderr,
                    )
            if not plan:
                print("No more spans pending enrichment.")
                break

            if args.dry_run_plan:
                print(f"[enrichment] dry-run plan (limit={this_batch}):")
                for idx, item in enumerate(plan, start=1):
                    print(
                        f"  {idx}. span_hash={item['span_hash']} "
                        f"path={item.get('path', '<unknown>')} "
                        f"lines={item.get('lines')}",
                        file=sys.stderr,
                    )
                return 0

            total_spans = len(plan)
            for idx, item in enumerate(plan, start=1):
                attempted += 1
                wall_start = time.monotonic()
                prompt = build_prompt(item, repo_root)
                if args.dry_run:
                    print(f"DRY RUN span {item['span_hash']} -> prompt preview:\n{prompt}\n")
                    continue

                line_start, line_end = item["lines"]
                snippet = item.get("code_snippet", "") or ""
                line_count = int(line_end - line_start + 1)
                nesting_depth = estimate_nesting_depth(snippet)
                node_count, schema_depth = estimate_json_nodes_and_depth(snippet)
                tokens_in = estimate_tokens_from_text(prompt)
                tokens_out = expected_output_tokens(item)

                router_metrics: dict[str, float] = {
                    "line_count": float(line_count),
                    "nesting_depth": float(nesting_depth),
                    "node_count": float(node_count),
                    "schema_depth": float(schema_depth),
                    "tokens_in": float(tokens_in),
                    "tokens_out": float(tokens_out),
                }
                rag_k_val = item.get("retrieved_count")
                if isinstance(rag_k_val, (int, float)):
                    router_metrics["rag_k"] = float(rag_k_val)
                rag_avg_val = item.get("retrieved_avg_score")
                if isinstance(rag_avg_val, (int, float)):
                    router_metrics["rag_avg_score"] = float(rag_avg_val)

                manual_override = (args.start_tier or "auto").lower()
                if router_enabled:
                    start_tier = choose_start_tier(
                        router_metrics, settings, override=args.start_tier
                    ).lower()
                    if manual_override != "auto":
                        start_tier = manual_override
                    if line_count >= policy_line_threshold and start_tier != policy_fallback_tier:
                        start_tier = policy_fallback_tier
                else:
                    start_tier = (
                        manual_override if manual_override != "auto" else policy_default_tier
                    )
                if start_tier not in {"7b", "14b", "nano"}:
                    start_tier = policy_default_tier

                base_attempts = max(1, min(args.retries, policy_max_retries))
                if backend in {"auto", "ollama"}:
                    per_host_attempts = 2 if router_enabled else 1
                    required_attempts = host_chain_count * per_host_attempts
                    max_attempts = max(base_attempts, required_attempts)
                else:
                    max_attempts = base_attempts
                schema_failures = 0
                tiers_history: list[str] = []
                attempt_records: list[dict[str, Any]] = []
                current_tier = start_tier
                success = False
                final_result: dict[str, object] | None = None
                final_meta: dict[str, object] = {}
                failure_info: tuple[str, object, object] | None = None
                attempt_idx = 0
                current_host_idx = 0

                # Router Integration (SDD v2.1 Phase 2)
                route_specs: Sequence[EnrichmentBackendSpecT] | None = None
                if enrichment_router:
                    try:
                        slice_view = EnrichmentSliceView(
                            span_hash=item["span_hash"],
                            file_path=Path(item["path"]),
                            start_line=line_start,
                            end_line=line_end,
                            content_type=item.get("slice_type", "unknown"),
                            classifier_confidence=item.get("classifier_confidence", 0.0),
                            approx_token_count=tokens_in,
                        )
                        decision = enrichment_router.choose_chain(
                            slice_view,
                            chain_override=args.chain_name,
                        )
                        enrichment_router.log_decision(decision, item["span_hash"])
                        route_specs = decision.backend_specs
                        if args.verbose and decision.reasons:
                            print(
                                f"  [router] {item['span_hash'][:8]} -> chain={decision.chain_name!r} reasons={decision.reasons}",
                                file=sys.stderr,
                            )
                    except Exception as exc:
                        if args.verbose:
                            print(
                                f"  [router] routing failed for {item['span_hash'][:8]}: {exc}",
                                file=sys.stderr,
                            )
                        route_specs = None

                while attempt_idx < max_attempts:
                    attempt_idx += 1
                    tier_for_attempt = current_tier or start_tier
                    tiers_history.append(tier_for_attempt)

                    (
                        cascade,
                        preset_key,
                        tier_preset,
                        host_label,
                        host_url,
                        selected_backend,
                        chain_name_used,
                    ) = _build_cascade_for_attempt(
                        backend=backend,
                        tier_for_attempt=tier_for_attempt,
                        repo_root=repo_root,
                        args=args,
                        ollama_host_chain=ollama_host_chain,
                        current_host_idx=current_host_idx,
                        host_chain_count=host_chain_count,
                        enrichment_config=enrichment_config,
                        selected_chain=selected_chain,
                        backend_specs=route_specs,
                    )

                    options = tier_preset.get("options") if selected_backend == "ollama" else None
                    tier_model_override = (
                        tier_preset.get("model") if selected_backend == "ollama" else None
                    )

                    sampler: _GpuSampler | None = None
                    if _should_sample_local_gpu(selected_backend, host_url):
                        sampler = _GpuSampler()
                        sampler.start()
                    attempt_start = time.monotonic()
                    try:
                        result, meta, backend_attempts = cascade.generate_for_span(
                            prompt,
                            item=item,
                        )
                    except BackendError as exc:
                        gpu_stats = sampler.stop() if sampler else {}
                        attempt_duration = time.monotonic() - attempt_start

                        # Runtime-equivalent path: underlying call_qwen raised.
                        if exc.failure is None:
                            attempt_records.append(
                                {
                                    "tier": tier_for_attempt,
                                    "duration": attempt_duration,
                                    "gpu": gpu_stats,
                                    "success": False,
                                    "failure": "runtime",
                                    "options": options,
                                    "model": tier_model_override,
                                    "host": host_label or host_url,
                                    "chain_name": chain_name_used,
                                }
                            )
                            if router_enabled and tier_for_attempt != policy_fallback_tier:
                                current_tier = policy_fallback_tier
                                continue
                            if (
                                selected_backend == "ollama"
                                and (not router_enabled or tier_for_attempt == policy_fallback_tier)
                                and current_host_idx + 1 < host_chain_count
                            ):
                                current_host_idx += 1
                                current_tier = start_tier
                                time.sleep(args.retry_wait)
                                continue
                            if attempt_idx < max_attempts:
                                time.sleep(args.retry_wait)
                                continue
                            break

                        # Non-runtime failure (validation/parse/truncation/etc.).
                        failure_info = exc.failure
                        failure_type = classify_failure(failure_info)
                        last_attempt = exc.attempts[-1] if exc.attempts else None
                        last_model = getattr(last_attempt, "model", None) if last_attempt else None
                        last_host = getattr(last_attempt, "host", None) if last_attempt else None
                        attempt_records.append(
                            {
                                "tier": tier_for_attempt,
                                "duration": attempt_duration,
                                "gpu": gpu_stats,
                                "success": False,
                                "failure": failure_type,
                                "options": options,
                                "model": last_model or tier_model_override,
                                "host": last_host or host_label or host_url,
                                "chain_name": chain_name_used
                                or (meta.get("chain_name") if isinstance(meta, dict) else None),
                            }
                        )
                        if failure_type == "validation":
                            schema_failures += 1

                        # Always allow promotion to fallback tier on repeated validation
                        # failures, even when router heuristics are disabled.
                        promote_due_to_schema = (
                            schema_failures >= policy_schema_threshold
                            and tier_for_attempt != policy_fallback_tier
                        )
                        promote_due_to_size = (
                            router_enabled
                            and line_count >= policy_line_threshold
                            and tier_for_attempt != policy_fallback_tier
                        )
                        promote_due_to_failure = (
                            router_enabled
                            and failure_type in {"runtime", "parse", "truncation"}
                            and tier_for_attempt != policy_fallback_tier
                        )
                        if promote_due_to_schema or promote_due_to_size or promote_due_to_failure:
                            current_tier = policy_fallback_tier
                            continue
                        if (
                            selected_backend == "ollama"
                            and (not router_enabled or tier_for_attempt == policy_fallback_tier)
                            and current_host_idx + 1 < host_chain_count
                        ):
                            current_host_idx += 1
                            current_tier = start_tier
                            time.sleep(args.retry_wait)
                            continue
                        if attempt_idx < max_attempts:
                            time.sleep(args.retry_wait)
                            continue
                        break

                    gpu_stats = sampler.stop() if sampler else {}
                    attempt_duration = time.monotonic() - attempt_start
                    success = True
                    final_result = result
                    final_meta = {
                        **meta,
                        "gpu_stats": gpu_stats,
                        "options": options,
                        "tier_key": preset_key,
                    }
                    attempt_records.append(
                        {
                            "tier": tier_for_attempt,
                            "duration": attempt_duration,
                            "gpu": gpu_stats,
                            "success": True,
                            "failure": None,
                            "options": options,
                            "model": meta.get("model") if isinstance(meta, dict) else None,
                            "host": meta.get("host", host_label or host_url)
                            if isinstance(meta, dict)
                            else (host_label or host_url),
                            "chain_name": meta.get("chain_name", chain_name_used)
                            if isinstance(meta, dict)
                            else chain_name_used,
                        }
                    )
                    break
                router_tier = tiers_history[-1] if tiers_history else start_tier
                final_tier = (
                    infer_effective_tier(final_meta, router_tier) if success else router_tier
                )
                promo_label = "none"
                if len(tiers_history) > 1:
                    promo_label = f"{tiers_history[0]}->{tiers_history[-1]}"

                total_latency = time.monotonic() - wall_start

                if not success and failure_tracker is not None:
                    # Record span-level failure in shared failure cache so the daemon
                    # can skip obviously broken spans on future cycles.
                    try:
                        failure_reason = failure_info[0] if failure_info else "unknown"
                        failure_tracker.record_failure(
                            item["span_hash"],
                            repo_key,
                            str(failure_reason),
                        )
                    except Exception:
                        # Failure tracking is best-effort; never crash enrichment on it.
                        pass

                last_attempt_dict: dict[str, Any] = attempt_records[-1] if attempt_records else {}
                gpu_stats_last: dict[str, float | None] = {}
                if isinstance(final_meta.get("gpu_stats"), dict):
                    gpu_stats_last = final_meta["gpu_stats"]  # type: ignore[assignment]
                elif isinstance(last_attempt_dict.get("gpu"), dict):
                    gpu_stats_last = last_attempt_dict["gpu"]  # type: ignore[assignment]

                tier_options = final_meta.get("options") if isinstance(final_meta, dict) else None
                if not isinstance(tier_options, dict):
                    tier_options = last_attempt_dict.get("options")
                if not isinstance(tier_options, dict):
                    tier_options = {}

                result_model = None
                if success:
                    if isinstance(final_meta.get("model"), str):
                        result_model = final_meta["model"]  # type: ignore[index]
                    elif isinstance(last_attempt_dict.get("model"), str):
                        result_model = last_attempt_dict["model"]  # type: ignore[assignment]
                    elif final_result and isinstance(final_result.get("model"), str):
                        result_model = final_result.get("model")
                    if not result_model:
                        result_model = args.model
                else:
                    if isinstance(last_attempt_dict.get("model"), str):
                        result_model = last_attempt_dict["model"]  # type: ignore[assignment]
                    else:
                        result_model = args.fallback_model or os.environ.get(
                            "OLLAMA_MODEL", policy_default_tier
                        )

                gpu_avg = (
                    gpu_stats_last.get("avg_util") if isinstance(gpu_stats_last, dict) else None
                )
                gpu_max = (
                    gpu_stats_last.get("max_util") if isinstance(gpu_stats_last, dict) else None
                )
                vram_peak = (
                    gpu_stats_last.get("max_mem") if isinstance(gpu_stats_last, dict) else None
                )
                vram_avg = (
                    gpu_stats_last.get("avg_mem") if isinstance(gpu_stats_last, dict) else None
                )
                ctx_value = tier_options.get("num_ctx") if isinstance(tier_options, dict) else None
                batch_value = (
                    tier_options.get("num_batch") if isinstance(tier_options, dict) else None
                )
                num_thread_value = (
                    tier_options.get("num_thread") if isinstance(tier_options, dict) else None
                )
                num_gpu_value = (
                    tier_options.get("num_gpu") if isinstance(tier_options, dict) else None
                )
                rss_mib = _read_rss_mib()
                tok_s = None
                eval_count = final_meta.get("eval_count") if isinstance(final_meta, dict) else None
                if isinstance(eval_count, int) and total_latency > 0:
                    tok_s = round(eval_count / total_latency, 2)
                elif success and total_latency > 0:
                    tok_s = round(tokens_out / total_latency, 2)

                metrics_summary = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "repo_root": str(repo_root),
                    "span_hash": item["span_hash"],
                    "path": item["path"],
                    "duration_sec": round(total_latency, 3),
                    "model": result_model,
                    "tier": final_tier,
                    "router_tier": router_tier,
                    "schema_ok": success,
                    "tok_s": tok_s,
                    "gpu_util": gpu_avg,
                    "gpu_util_max": gpu_max,
                    "vram_mib": vram_peak,
                    "vram_avg_mib": vram_avg,
                    "rss_mib": rss_mib,
                    "ctx": ctx_value,
                    "batch": batch_value,
                    "num_thread": num_thread_value,
                    "num_gpu": num_gpu_value,
                    "attempts": len(attempt_records) or attempt_idx,
                    "estimated_tokens_per_span": get_est_tokens_per_span(REPO_ROOT),
                }
                for field in policy_log_fields:
                    metrics_summary.setdefault(field, metrics_summary.get(field))

                ledger_record = {
                    "timestamp": metrics_summary["timestamp"],
                    "task_id": item["span_hash"],
                    "path": item["path"],
                    "tier_used": final_tier,
                    "router_tier": router_tier,
                    "line_count": line_count,
                    "nesting_depth": nesting_depth,
                    "node_count": node_count,
                    "schema_depth": schema_depth,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "k": router_metrics.get("rag_k"),
                    "avg_score": router_metrics.get("rag_avg_score"),
                    "promo": promo_label,
                    "schema_ok": success,
                    "tok_s": tok_s,
                    "gpu_util": gpu_avg,
                    "gpu_util_max": gpu_max,
                    "vram_mib": vram_peak,
                    "ctx": ctx_value,
                    "batch": batch_value,
                    "num_thread": num_thread_value,
                    "num_gpu": num_gpu_value,
                    "rss_mib": rss_mib,
                    "attempts": len(attempt_records) or attempt_idx,
                    "wall_ms": int(round(total_latency * 1000)),
                    "result_model": result_model,
                }

                if success and final_result is not None:
                    ledger_record["result"] = "pass"
                    ledger_record["reason"] = "success"
                    final_result.setdefault("model", result_model)
                    final_result.setdefault("schema_version", args.schema_version)
                    db.store_enrichment(item["span_hash"], final_result)
                    db.conn.commit()

                    stats = db.stats()
                    metrics_summary["spans_total"] = stats["spans"]
                    metrics_summary["enrichments_total"] = stats["enrichments"]
                    metrics_summary["estimated_remote_tokens_saved"] = stats[
                        "enrichments"
                    ] * get_est_tokens_per_span(REPO_ROOT)
                    metrics_summary["estimated_remote_tokens_repo_cap"] = stats[
                        "spans"
                    ] * get_est_tokens_per_span(REPO_ROOT)

                    processed += 1

                # Heartbeat for long-running batches so foreground/daemon logs show progress.
                if total_spans:
                    if idx == 1 or idx == total_spans or idx % 10 == 0:
                        print(
                            f"[rag-enrich] Enriched span {idx}/{total_spans} "
                            f"for {item.get('path', '<unknown>')}",
                            flush=True,
                        )
                    model_note = f" ({result_model})" if result_model else ""
                    router_note = ""
                    if final_tier != router_tier:
                        router_note = f" [router {router_tier}]"

                    # Extract config metadata for logging
                    chain_name = (
                        final_meta.get("chain_name") if isinstance(final_meta, dict) else None
                    )
                    backend_name = (
                        final_meta.get("backend_name") if isinstance(final_meta, dict) else None
                    )
                    host_url_for_log: str | None
                    if isinstance(final_meta, dict):
                        raw_host = final_meta.get("host_url")
                        host_url_for_log = str(raw_host) if isinstance(raw_host, str) else None
                    else:
                        host_url_for_log = None

                    config_note = ""
                    if chain_name or backend_name or host_url_for_log:
                        parts = []
                        if chain_name:
                            parts.append(f"chain={chain_name}")
                        if backend_name:
                            parts.append(f"backend={backend_name}")
                        if host_url_for_log:
                            parts.append(f"url={host_url_for_log}")
                        config_note = f" [{', '.join(parts)}]"

                    print(
                        f"Stored enrichment {processed}: {item['path']}:{item['lines'][0]}-{item['lines'][1]} "
                        f"({total_latency:.2f}s) via tier {final_tier}{model_note}{router_note}{config_note}"
                    )
                    if args.sleep:
                        time.sleep(args.sleep)
                else:
                    ledger_record["result"] = "fail"
                    failed += 1
                    failure_reason = failure_info[0] if failure_info else "unknown"
                    ledger_record["reason"] = failure_reason
                    if failure_info is None:
                        failure_info = ("unknown", "Unknown failure", None)
                    handle_failure(repo_root, item, failure_info)

                append_metrics(log_path, metrics_summary)
                append_ledger_record(ledger_path, ledger_record)
    finally:
        db.close()

    summary = {
        "attempted": attempted,
        "succeeded": processed,
        "failed": failed,
        "mode": pipeline_mode,
        "chain": effective_chain,
        "backend": backend,
        "repo_root": str(repo_root),
    }
    print(
        f"[enrichment] run summary: attempted={summary['attempted']} "
        f"succeeded={summary['succeeded']} failed={summary['failed']} "
        f"mode={summary['mode']} chain={summary['chain'] or '-'} backend={summary['backend']}",
        file=sys.stderr,
    )
    if summary_json_path:
        try:
            with open(summary_json_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, sort_keys=True)
        except OSError as exc:
            if args.verbose:
                print(
                    f"[enrichment] failed to write summary JSON to {summary_json_path}: {exc}",
                    file=sys.stderr,
                )

    print(f"Completed {processed} enrichments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
