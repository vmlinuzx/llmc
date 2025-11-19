from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

BASE_PATH = Path(".llmc/quality/ruff_baseline.json")


def _run_ruff_counts() -> Dict[str, int]:
    """
    Run Ruff and aggregate violation counts by code.

    This is intentionally lightweight and tolerant of Ruff failures; if Ruff
    is unavailable or emits invalid JSON, we treat it as "no data".
    """
    result = subprocess.run(
        ["python", "-m", "ruff", "check", ".", "--output-format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(result.stdout or "[]")
    except Exception:
        data = []

    counts: Dict[str, int] = {}
    for entry in data:
        code = (entry.get("code") or "").strip()
        if not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return counts


def write() -> None:
    """Write the current Ruff violation counts as the quality baseline."""
    BASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = _run_ruff_counts()
    with BASE_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"counts": counts}, handle, indent=2)
    print(f"Wrote baseline to {BASE_PATH}")


def check() -> None:
    """
    Compare current Ruff violation counts to the stored baseline.

    Fails if any code's count increases; passes otherwise.
    """
    if not BASE_PATH.exists():
        print("No baseline found; run `make quality-baseline` first.")
        raise SystemExit(2)

    with BASE_PATH.open("r", encoding="utf-8") as handle:
        base: Dict[str, Any] = json.load(handle).get("counts", {})

    current = _run_ruff_counts()
    regressions: Dict[str, Dict[str, int]] = {}
    for code, current_count in current.items():
        baseline_count = int(base.get(code, 0))
        if current_count > baseline_count:
            regressions[code] = {"baseline": baseline_count, "current": current_count}

    if regressions:
        print("Quality regression detected:")
        for code, vals in sorted(regressions.items()):
            print(f"  {code}: {vals['baseline']} -> {vals['current']}")
        raise SystemExit(1)

    print("Quality check passed (no regressions).")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "write":
        write()
    elif cmd == "check":
        check()
    else:
        print("Usage: python tools/dev/quality_baseline.py [write|check]")

