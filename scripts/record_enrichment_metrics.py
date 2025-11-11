#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.rag.database import Database
from tools.rag.workers import validate_enrichment

EST_TOKENS_PER_SPAN = 350  # keep in sync with tools.rag.cli.EST_TOKENS_PER_SPAN


def find_repo_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            cwd=start,
        )
    except FileNotFoundError:
        result = None

    if result and result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())

    cur = start.resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    return start


def _load_plan(plan_path: Path) -> dict:
    raw = plan_path.read_text(encoding="utf-8")
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Could not locate JSON array in {plan_path}")
    plan = json.loads(raw[start : end + 1])
    if not plan:
        raise ValueError(f"Plan at {plan_path} is empty")
    return plan[0]


def _append_metrics(log_path: Path, metrics: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate, store, and log enrichment metadata."
    )
    parser.add_argument("--plan", required=True, type=Path, help="Path to enrichment plan JSON")
    parser.add_argument("--payload", required=True, type=Path, help="Path to LLM enrichment payload JSON")
    parser.add_argument("--latency", required=True, type=float, help="Wall-clock latency in seconds")
    parser.add_argument(
        "--log",
        default="logs/enrichment_metrics.jsonl",
        type=Path,
        help="Append metrics to this JSONL file (default: logs/enrichment_metrics.jsonl)",
    )
    parser.add_argument("--model", default="qwen2.5:14b", help="Model identifier to store with enrichment")
    parser.add_argument(
        "--schema-version",
        default="enrichment.v1",
        dest="schema_version",
        help="Schema version to tag the enrichment with",
    )
    args = parser.parse_args()

    plan = _load_plan(args.plan)
    payload = json.loads(args.payload.read_text(encoding="utf-8"))

    repo_root = find_repo_root()
    database_path = repo_root / ".rag" / "index.db"
    db = Database(database_path)
    try:
        ok, errors = validate_enrichment(payload, plan["lines"][0], plan["lines"][1])
        if not ok:
            for err in errors:
                print(f"validation error: {err}", file=sys.stderr)
            return 1
        payload.setdefault("model", args.model)
        payload.setdefault("schema_version", args.schema_version)
        db.store_enrichment(plan["span_hash"], payload)
        db.conn.commit()
        stats = db.stats()
    finally:
        db.close()

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "span_hash": plan["span_hash"],
        "path": plan["path"],
        "latency_sec": args.latency,
        "model": payload.get("model"),
        "estimated_tokens_per_span": EST_TOKENS_PER_SPAN,
        "estimated_remote_tokens_saved": stats["enrichments"] * EST_TOKENS_PER_SPAN,
        "estimated_remote_tokens_repo_cap": stats["spans"] * EST_TOKENS_PER_SPAN,
        "spans_total": stats["spans"],
        "enrichments_total": stats["enrichments"],
    }
    _append_metrics(args.log, metrics)
    print(
        f"Stored enrichment for {plan['span_hash']} with latency {args.latency:.2f}s.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
