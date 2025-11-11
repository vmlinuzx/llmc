#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Iterable, List, Tuple


def load_entries(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"No metrics file found at {path}")
    entries: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON entry in {path}: {exc}") from exc
    if not entries:
        raise ValueError(f"Metrics file {path} is empty.")
    return entries


def summarize_latencies(entries: Iterable[dict]) -> Tuple[float, float, float]:
    values = [float(entry["latency_sec"]) for entry in entries]
    return min(values), max(values), mean(values)


def summarize_tokens(entries: Iterable[dict]) -> Tuple[int, int, float, int]:
    per_span = [int(entry["estimated_tokens_per_span"]) for entry in entries]
    saved_totals = []
    repo_caps = []
    for entry in entries:
        per_span_tokens = int(entry["estimated_tokens_per_span"])
        saved_value = entry.get("estimated_remote_tokens_saved")
        if saved_value is None:
            saved_value = int(entry.get("enrichments_total", 0)) * per_span_tokens
        saved_totals.append(int(saved_value))
        repo_value = entry.get("estimated_remote_tokens_repo_cap")
        if repo_value is None:
            repo_value = int(entry.get("spans_total", 0)) * per_span_tokens
        repo_caps.append(int(repo_value))
    return (
        max(per_span) if per_span else 0,
        max(saved_totals) if saved_totals else 0,
        mean(per_span) if per_span else 0.0,
        max(repo_caps) if repo_caps else 0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize enrichment latency/token metrics from JSONL log."
    )
    parser.add_argument(
        "--log",
        default="logs/enrichment_metrics.jsonl",
        type=Path,
        help="Path to metrics JSONL file (default: logs/enrichment_metrics.jsonl)",
    )
    args = parser.parse_args()

    entries = load_entries(args.log)
    latency_min, latency_max, latency_avg = summarize_latencies(entries)
    token_cap, tokens_saved, token_avg, repo_cap = summarize_tokens(entries)

    print(f"Entries analyzed: {len(entries)}")
    print(f"Latency  (s): min={latency_min:.2f} max={latency_max:.2f} avg={latency_avg:.2f}")
    print(
        f"Tokens per span heuristic: mean={token_avg:.0f} max={token_cap} "
        f"(cumulative saved ≈ {tokens_saved:,}; repo cap ≈ {repo_cap:,})"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
