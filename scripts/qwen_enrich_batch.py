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
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.rag.database import Database
from tools.rag.workers import enrichment_plan, validate_enrichment

EST_TOKENS_PER_SPAN = 350  # keep in sync with tools.rag.cli


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
        default="qwen2.5:14b",
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
    return parser.parse_args()


def ensure_repo(repo_root: Path) -> Path:
    repo_root = repo_root.resolve()
    if not (repo_root / ".git").exists():
        raise SystemExit(f"{repo_root} does not look like a git repo (missing .git/).")
    return repo_root


def build_prompt(item: Dict, repo_root: Path) -> str:
    path = item["path"]
    lang = item.get("lang", "").lower()
    line_start, line_end = item["lines"]
    snippet = item.get("code_snippet", "")

    language_hint = ""
    if lang in {"python"}:
        language_hint = "Include function signature details such as arguments and return behavior."
    elif lang in {"typescript", "javascript", "tsx", "jsx"}:
        language_hint = "Describe props, return values, and side effects relevant to the component or function."
    elif lang in {"html"}:
        language_hint = "Reference tag attributes and semantic roles directly."
    elif lang in {"sql"}:
        language_hint = "Explain selected columns, filters, and mutations described by the SQL."

    prompt = f"""You are Qwen2.5 performing code enrichment for repository documentation. Produce ONLY compact JSON with keys:
{{
  "summary_120w": string (<=120 words),
  "inputs": array of strings,
  "outputs": array of strings,
  "side_effects": array of strings,
  "pitfalls": array of strings,
  "usage_snippet": string or null (<=12 words),
  "evidence": array of {{"field": string, "lines": [start,end]}}
}}
Rules:
- Summarize precisely what the code does, including important options/defaults from the snippet.
- In "inputs", list real parameters or data dependencies; use [] if none. Outputs should describe return values or major results.
- Provide at least one evidence entry for "summary_120w". Every other populated field must also have at least one evidence entry, with line ranges between {line_start} and {line_end} (inclusive) and matching field names.
- Do not include evidence entries for fields left [] or null.
- Use [] or null when a claim cannot be supported.
- Output strict minified JSON with double quotes only. {language_hint}

Context:
File: {path}
Lines {line_start}-{line_end}:
<<<
{snippet}
>>>

Deliverable: ONLY the JSON object."""
    return prompt


def call_qwen(
    prompt: str,
    repo_root: Path,
    verbose: bool = False,
    retries: int = 3,
    retry_wait: float = 2.0,
    poll_wait: float = 1.5,
) -> str:
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model_name = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M")
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
                return combined
            last_error = ValueError("Failed to parse Ollama response")
        else:
            response_text = data.get("response", "")
            if isinstance(response_text, str) and response_text.strip():
                return response_text
            last_error = ValueError("No response from Ollama")

        if attempt < max(1, retries):
            time.sleep(max(0.0, retry_wait))
    assert last_error is not None
    raise last_error


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


def append_metrics(log_path: Path, metrics: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    args = parse_args()
    repo_root = ensure_repo(args.repo)
    log_path = args.log or (repo_root / "logs" / "enrichment_metrics.jsonl")

    db_file = repo_root / ".rag" / "index.db"
    db = Database(db_file)
    processed = 0
    try:
        while True:
            remaining = args.max_spans - processed if args.max_spans else None
            if remaining is not None and remaining <= 0:
                break
            this_batch = args.batch_size if remaining is None else min(args.batch_size, remaining)
            plan = enrichment_plan(db, repo_root, limit=this_batch)
            if not plan:
                print("No more spans pending enrichment.")
                break

            for item in plan:
                start_time = time.monotonic()
                prompt = build_prompt(item, repo_root)
                if args.dry_run:
                    print(f"DRY RUN span {item['span_hash']} -> prompt preview:\n{prompt}\n")
                    continue

                try:
                    stdout = call_qwen(
                        prompt,
                        repo_root,
                        verbose=args.verbose,
                        retries=args.retries,
                        retry_wait=args.retry_wait,
                    )
                except RuntimeError as exc:
                    print(
                        f"codex_wrap error for {item['span_hash']} ({item['path']}:{item['lines']}): {exc}",
                        file=sys.stderr,
                    )
                    continue
                result = extract_json(stdout)
                normalize_evidence(result, item["lines"][0], item["lines"][1])
                ok, errors = validate_enrichment(
                    result, item["lines"][0], item["lines"][1]
                )
                if not ok:
                    print(
                        f"Validation failed for {item['span_hash']} ({item['path']}:{item['lines']}): {errors}",
                        file=sys.stderr,
                    )
                    continue

                latency = time.monotonic() - start_time
                result.setdefault("model", args.model)
                result.setdefault("schema_version", args.schema_version)
                db.store_enrichment(item["span_hash"], result)
                db.conn.commit()

                metrics = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "repo_root": str(repo_root),
                    "span_hash": item["span_hash"],
                    "path": item["path"],
                    "latency_sec": round(latency, 3),
                    "model": result.get("model"),
                    "estimated_tokens_per_span": EST_TOKENS_PER_SPAN,
                }
                stats = db.stats()
                metrics["spans_total"] = stats["spans"]
                metrics["enrichments_total"] = stats["enrichments"]
                metrics["estimated_remote_tokens_saved"] = (
                    stats["enrichments"] * EST_TOKENS_PER_SPAN
                )
                metrics["estimated_remote_tokens_repo_cap"] = (
                    stats["spans"] * EST_TOKENS_PER_SPAN
                )
                append_metrics(log_path, metrics)

                processed += 1
                print(
                    f"Stored enrichment {processed}: {item['path']}:{item['lines'][0]}-{item['lines'][1]} "
                    f"({latency:.2f}s)"
                )
                if args.sleep:
                    time.sleep(args.sleep)
    finally:
        db.close()

    print(f"Completed {processed} enrichments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
