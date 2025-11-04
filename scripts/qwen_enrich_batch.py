#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from router import (
    RouterSettings,
    clamp_usage_snippet,
    classify_failure,
    choose_next_tier_on_failure,
    choose_start_tier,
    detect_truncation,
    estimate_json_nodes_and_depth,
    estimate_nesting_depth,
    estimate_tokens_from_text,
    expected_output_tokens,
)

from tools.rag.database import Database
from tools.rag.workers import enrichment_plan, validate_enrichment

EST_TOKENS_PER_SPAN = 350  # keep in sync with tools.rag.cli
GATEWAY_DEFAULT_TIMEOUT = 300.0

_TRUTHY = {"1", "true", "yes", "on"}


def env_flag(name: str, env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    raw = env.get(name, "").strip().lower()
    return raw in _TRUTHY


def azure_env_available(env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT"]
    return all(env.get(key) for key in required)


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
    return parser.parse_args()


def ensure_repo(repo_root: Path) -> Path:
    repo_root = repo_root.resolve()
    if not (repo_root / ".git").exists():
        raise SystemExit(f"{repo_root} does not look like a git repo (missing .git/).")
    return repo_root


def build_prompt(item: Dict, repo_root: Path) -> str:
    path = item["path"]
    line_start, line_end = item["lines"]
    snippet = item.get("code_snippet", "")

    prompt = f"""Return ONLY minified JSON:
{{"summary_120w":"<what it does>","inputs":["params"],"outputs":["returns"],"side_effects":["mutations"],"pitfalls":["gotchas"],"usage_snippet":"brief example","evidence":[{{"field":"summary_120w","lines":[{line_start},{line_end}]}}]}}

Rules: summary<=120w, evidence for each populated field with lines [{line_start}-{line_end}], [] or null if unsupported.

{path} L{line_start}-{line_end}:
{snippet}

JSON only:"""
    return prompt


def call_via_ollama(
    prompt: str,
    repo_root: Path,
    verbose: bool = False,
    retries: int = 3,
    retry_wait: float = 2.0,
    poll_wait: float = 1.5,
    model_override: str | None = None,
) -> Tuple[str, Dict[str, object]]:
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model_name = model_override or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    payload = json.dumps({"model": model_name, "prompt": prompt, "stream": False}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    def runner_active() -> bool:
        try:
            output = subprocess.check_output(["ollama", "ps"], text=True)
        except Exception:
            return False
        return model_name in output

    while runner_active():
        time.sleep(max(0.5, poll_wait))

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
                }
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
                }
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
) -> Tuple[str, Dict[str, object]]:
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(repo_root),
        env=env,
        timeout=timeout,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"llm gateway failed (exit {proc.returncode}): {proc.stderr.strip() or 'no stderr'}"
        )
    output = proc.stdout.strip()
    if not output:
        raise RuntimeError("llm gateway returned empty output")
    meta: Dict[str, object] = {
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
) -> Tuple[str, Dict[str, str]]:
    backend = backend or "auto"
    backend = backend.lower()
    env = os.environ
    prefer_gateway = (
        backend == "gateway"
        or (
            backend == "auto"
            and (
                azure_env_available(env)
                or env_flag("LLM_GATEWAY_DISABLE_LOCAL", env)
                or env_flag("LLM_GATEWAY_FORCE_GATEWAY", env)
            )
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
                env.get("AZURE_OPENAI_DEPLOYMENT") if azure_env_available(env) else env.get("GEMINI_MODEL", "gemini")
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
        model_label = model_override or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
        output, meta = call_via_ollama(
            prompt,
            repo_root,
            verbose=verbose,
            retries=retries,
            retry_wait=retry_wait,
            poll_wait=poll_wait,
            model_override=model_override,
        )
        meta.setdefault("backend", "ollama")
        meta.setdefault("model", model_label)
        return output, meta
    except Exception as exc:
        errors.append(exc)
        if errors:
            msgs = "; ".join(str(e) for e in errors)
            raise RuntimeError(msgs) from exc
        raise


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
    filtered: List[dict] = []
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


def parse_and_validate(
    raw: str,
    item: Dict,
    meta: Dict[str, object],
) -> Tuple[Dict | None, Tuple[str, object, object] | None]:
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

    clamp_usage_snippet(result, max_lines=12)
    normalize_evidence(result, item["lines"][0], item["lines"][1])
    ok, errors = validate_enrichment(result, item["lines"][0], item["lines"][1])
    if not ok:
        return None, ("validation", errors, result)

    return result, None


def handle_failure(repo_root: Path, item: Dict, failure: Tuple[str, object, object]) -> None:
    kind, detail, payload = failure
    if kind in {"parse", "truncation"}:
        raw = payload if isinstance(payload, str) else ""
        log_dir = repo_root / "logs" / "failed_enrichments"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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


def main() -> int:
    args = parse_args()
    repo_root = ensure_repo(args.repo)
    backend = args.backend
    if args.api:
        backend = "gateway"
    elif args.local:
        backend = "ollama"

    if args.verbose:
        print(f"Backend selection: {backend}", file=sys.stderr)

    if args.cooldown:
        print(f"Cooldown: skipping spans modified within last {args.cooldown}s", file=sys.stderr)
    log_path = args.log or (repo_root / "logs" / "enrichment_metrics.jsonl")

    router_enabled = (args.router or "on").lower() != "off"
    settings = RouterSettings(headroom=args.max_tokens_headroom)
    promote_once_env = os.environ.get("ROUTER_PROMOTE_ONCE", "1").strip().lower()
    promote_once_flag = promote_once_env not in {"0", "false", "no", "off"}
    ledger_path = repo_root / "logs" / "run_ledger.log"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    db_file = repo_root / ".rag" / "index.db"
    db = Database(db_file)
    processed = 0
    try:
        while True:
            remaining = args.max_spans - processed if args.max_spans else None
            if remaining is not None and remaining <= 0:
                break
            this_batch = args.batch_size if remaining is None else min(args.batch_size, remaining)
            plan = enrichment_plan(db, repo_root, limit=this_batch, cooldown_seconds=args.cooldown)
            if not plan:
                print("No more spans pending enrichment.")
                break

            for item in plan:
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

                router_metrics: Dict[str, float] = {
                    "line_count": line_count,
                    "nesting_depth": nesting_depth,
                    "node_count": node_count,
                    "schema_depth": schema_depth,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "rag_k": item.get("retrieved_count"),
                    "rag_avg_score": item.get("retrieved_avg_score"),
                }

                if router_enabled:
                    start_tier = choose_start_tier(router_metrics, settings, override=args.start_tier)
                else:
                    manual_tier = (args.start_tier or "auto").lower()
                    start_tier = manual_tier if manual_tier != "auto" else "7b"

                tiers_history: List[str] = []
                current_tier = start_tier
                success = False
                final_result: Dict[str, object] | None = None
                final_meta: Dict[str, object] = {}
                failure_info: Tuple[str, object, object] | None = None

                while current_tier:
                    tiers_history.append(current_tier)
                    backend_choice = "gateway" if current_tier == "nano" else "ollama"
                    selected_backend = backend_choice if backend == "auto" else backend
                    tier_model_override: str | None = None
                    if selected_backend == "ollama":
                        if current_tier == "14b":
                            tier_model_override = (args.fallback_model or "qwen2.5:14b-instruct-q4_K_M")
                        elif current_tier == "7b":
                            tier_model_override = None

                    try:
                        stdout, meta = call_qwen(
                            prompt,
                            repo_root,
                            backend=selected_backend,
                            verbose=args.verbose,
                            retries=args.retries,
                            retry_wait=args.retry_wait,
                            poll_wait=1.5,
                            gateway_path=args.gateway_path,
                            gateway_timeout=args.gateway_timeout,
                            model_override=tier_model_override,
                        )
                    except RuntimeError as exc:
                        failure_info = ("runtime", exc, None)
                        if router_enabled:
                            next_tier = choose_next_tier_on_failure("runtime", current_tier, router_metrics, settings, promote_once=promote_once_flag)
                        else:
                            next_tier = None
                        if router_enabled and next_tier and next_tier not in tiers_history:
                            current_tier = next_tier
                            continue
                        break

                    result, failure = parse_and_validate(stdout, item, meta)
                    if result is not None:
                        success = True
                        final_result = result
                        final_meta = meta
                        break

                    failure_info = failure
                    failure_type = classify_failure(failure)
                    if router_enabled:
                        next_tier = choose_next_tier_on_failure(failure_type, current_tier, router_metrics, settings, promote_once=promote_once_flag)
                    else:
                        next_tier = None
                    if router_enabled and next_tier and next_tier not in tiers_history:
                        current_tier = next_tier
                        continue
                    break

                final_tier = tiers_history[-1] if tiers_history else start_tier
                promo_label = "none"
                if len(tiers_history) > 1:
                    promo_label = f"{tiers_history[0]}->{tiers_history[-1]}"

                ledger_record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task_id": item["span_hash"],
                    "path": item["path"],
                    "tier_used": final_tier,
                    "line_count": line_count,
                    "nesting_depth": nesting_depth,
                    "node_count": node_count,
                    "schema_depth": schema_depth,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "k": router_metrics.get("rag_k"),
                    "avg_score": router_metrics.get("rag_avg_score"),
                    "promo": promo_label,
                }

                if success and final_result is not None:
                    latency = time.monotonic() - wall_start
                    ledger_record["result"] = "pass"
                    ledger_record["reason"] = "success"
                    ledger_record["wall_ms"] = int(round(latency * 1000))

                    result_model = final_meta.get("model") or final_result.get("model") or args.model
                    final_result.setdefault("model", result_model)
                    final_result.setdefault("schema_version", args.schema_version)
                    db.store_enrichment(item["span_hash"], final_result)
                    db.conn.commit()

                    metrics_summary = {
                        "timestamp": ledger_record["timestamp"],
                        "repo_root": str(repo_root),
                        "span_hash": item["span_hash"],
                        "path": item["path"],
                        "latency_sec": round(latency, 3),
                        "model": result_model,
                        "tier": final_tier,
                        "estimated_tokens_per_span": EST_TOKENS_PER_SPAN,
                    }
                    stats = db.stats()
                    metrics_summary["spans_total"] = stats["spans"]
                    metrics_summary["enrichments_total"] = stats["enrichments"]
                    metrics_summary["estimated_remote_tokens_saved"] = stats["enrichments"] * EST_TOKENS_PER_SPAN
                    metrics_summary["estimated_remote_tokens_repo_cap"] = stats["spans"] * EST_TOKENS_PER_SPAN
                    append_metrics(log_path, metrics_summary)

                    processed += 1
                    print(
                        f"Stored enrichment {processed}: {item['path']}:{item['lines'][0]}-{item['lines'][1]} "
                        f"({latency:.2f}s) via tier {final_tier}"
                    )
                    if args.sleep:
                        time.sleep(args.sleep)
                else:
                    ledger_record["result"] = "fail"
                    failure_reason = failure_info[0] if failure_info else "unknown"
                    ledger_record["reason"] = failure_reason
                    ledger_record["wall_ms"] = int(round((time.monotonic() - wall_start) * 1000))
                    if failure_info is None:
                        failure_info = ("unknown", "Unknown failure", None)
                    handle_failure(repo_root, item, failure_info)

                append_ledger_record(ledger_path, ledger_record)
    finally:
        db.close()

    print(f"Completed {processed} enrichments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
