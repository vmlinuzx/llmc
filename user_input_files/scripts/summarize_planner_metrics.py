#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean


def load_entries(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"No planner log found at {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON line in {path}: {exc}") from exc
    if not records:
        raise ValueError(f"Planner log {path} is empty.")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize planner metrics JSONL (entries, mean confidence, fallback rate)."
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs/planner_metrics.jsonl"),
        help="Path to planner metrics JSONL (default: logs/planner_metrics.jsonl)",
    )
    args = parser.parse_args()

    entries = load_entries(args.log)
    confidences = [float(entry.get("confidence", 0.0)) for entry in entries]
    fallbacks = sum(1 for entry in entries if entry.get("fallback"))

    print(f"Entries analyzed: {len(entries)}")
    print(f"Confidence: min={min(confidences):.3f} max={max(confidences):.3f} avg={mean(confidences):.3f}")
    print(f"Fallback recommended: {fallbacks}/{len(entries)} ({fallbacks/len(entries)*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

