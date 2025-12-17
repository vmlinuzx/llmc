"""
llmc_mcp.benchmarks.runner

M6 Benchmarks: a tiny, dependency-free harness to time MCP-side tools.
- Calls wrappers directly (no stdio integration required).
- Emits a CSV file to ./metrics/benchmarks_YYYYmmdd_HHMMSS.csv (or env override).
- Designed to be safe if TE/observability are absent; uses monkeypatchable call sites.

Usage:
    PYTHONPATH=. python -m llmc_mcp.benchmarks --quick
    PYTHONPATH=. python -m llmc_mcp.benchmarks --cases te_echo,repo_read_small,rag_top3

Env:
    LLMC_BENCH_OUTDIR=/path/to/metrics
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
import time
from typing import Any
import uuid

# Optional wrapper imports; tolerate absence for dry runs
try:
    from llmc_mcp.tools.te import te_run
except Exception:  # pragma: no cover
    te_run = None  # type: ignore

try:
    from llmc_mcp.tools.te_repo import rag_query, repo_read
except Exception:  # pragma: no cover
    repo_read = None  # type: ignore
    rag_query = None  # type: ignore

# Optional: observability reset is nice-to-have; ignore if missing
try:
    from llmc_mcp.observability import MetricsCollector  # type: ignore
except Exception:  # pragma: no cover
    MetricsCollector = None  # type: ignore


@dataclass
class BenchResult:
    bench_id: str
    case: str
    tool: str
    ok: bool
    returncode: int
    duration_s: float
    data_bytes: int
    note: str = ""


def _json_size(obj: Any) -> int:
    try:
        return len(json.dumps(obj))
    except Exception:
        return 0


def _now_stamp() -> str:
    import datetime as _dt

    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _outdir() -> str:
    od = os.getenv("LLMC_BENCH_OUTDIR") or "./metrics"
    os.makedirs(od, exist_ok=True)
    return od


def _emit_csv(rows: list[BenchResult]) -> str:
    path = os.path.join(_outdir(), f"benchmarks_{_now_stamp()}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        import csv as _csv

        w = _csv.writer(f)
        w.writerow(
            [
                "bench_id",
                "case",
                "tool",
                "ok",
                "returncode",
                "duration_s",
                "data_bytes",
                "note",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.bench_id,
                    r.case,
                    r.tool,
                    int(r.ok),
                    r.returncode,
                    f"{r.duration_s:.6f}",
                    r.data_bytes,
                    r.note,
                ]
            )
    return path


def _maybe_reset_metrics():
    if MetricsCollector is not None and hasattr(MetricsCollector, "reset"):
        try:
            MetricsCollector.reset()
        except Exception:
            pass


def case_te_echo() -> BenchResult:
    start = time.time()
    if te_run is None:
        return BenchResult(
            str(uuid.uuid4()),
            "te_echo",
            "te_run",
            False,
            -1,
            0.0,
            0,
            "te_run unavailable",
        )
    res = te_run(["run", "echo", "hello-bench"])
    dur = time.time() - start
    rc = int(res.get("meta", {}).get("returncode", -1))
    ok = rc == 0
    sz = _json_size(res.get("data"))
    return BenchResult(str(uuid.uuid4()), "te_echo", "te_run", ok, rc, dur, sz)


def case_repo_read_small() -> BenchResult:
    start = time.time()
    if repo_read is None:
        return BenchResult(
            str(uuid.uuid4()),
            "repo_read_small",
            "repo_read",
            False,
            -1,
            0.0,
            0,
            "repo_read unavailable",
        )
    res = repo_read(root=".", path="README.md", max_bytes=4096)
    dur = time.time() - start
    rc = int(res.get("meta", {}).get("returncode", -1))
    ok = rc == 0
    sz = _json_size(res.get("data"))
    return BenchResult(
        str(uuid.uuid4()), "repo_read_small", "repo_read", ok, rc, dur, sz
    )


def case_rag_top3() -> BenchResult:
    start = time.time()
    if rag_query is None:
        return BenchResult(
            str(uuid.uuid4()),
            "rag_top3",
            "rag_query",
            False,
            -1,
            0.0,
            0,
            "rag_query unavailable",
        )
    res = rag_query("bench: quick sanity", k=3)
    dur = time.time() - start
    rc = int(res.get("meta", {}).get("returncode", -1))
    ok = rc == 0
    sz = _json_size(res.get("data"))
    return BenchResult(str(uuid.uuid4()), "rag_top3", "rag_query", ok, rc, dur, sz)


CASES: dict[str, Callable[[], BenchResult]] = {
    "te_echo": case_te_echo,
    "repo_read_small": case_repo_read_small,
    "rag_top3": case_rag_top3,
}


def run_cases(selected: list[str] | None = None) -> list[BenchResult]:
    _maybe_reset_metrics()
    names = selected or list(CASES.keys())
    rows: list[BenchResult] = []
    for name in names:
        fn = CASES.get(name)
        if not fn:
            rows.append(
                BenchResult(
                    str(uuid.uuid4()), name, "-", False, -1, 0.0, 0, "unknown case"
                )
            )
            continue
        rows.append(fn())
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="LLMC MCP Benchmarks")
    p.add_argument("--cases", type=str, help="Comma-separated case names")
    p.add_argument(
        "--quick", action="store_true", help="Run a minimal set (te_echo only)"
    )
    args = p.parse_args(argv or [])

    if args.quick:
        selected = ["te_echo"]
    else:
        selected = args.cases.split(",") if args.cases else list(CASES.keys())

    rows = run_cases(selected)
    out = _emit_csv(rows)
    print(f"Wrote benchmark CSV: {out}")
    # Return non-zero if any case failed
    return 0 if all(r.ok for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
