from __future__ import annotations

from pathlib import Path

import pytest

from tools.rag.eval.search_eval import run

QUERIES = Path("DOCS/RAG_NAV/P9_Search/canary_queries.jsonl")
OUTDIR = Path(".llmc/eval")


@pytest.mark.slow
def test_search_eval_harness_runs_and_prefers_rag(tmp_path: Path):
    repo = Path(".").resolve()
    result = run(repo, QUERIES, OUTDIR, k=5, mode="both")
    summary = result["summary"]
    macro = summary["macro"]["tokens"]

    assert summary["n"] >= 1
    assert macro["rag"] is not None and macro["fallback"] is not None

    # Tolerant superiority check: allow small deviance (0.05) to avoid flakes.
    assert macro["rag"] + 0.05 >= macro["fallback"], (
        f"Expected RAG to be ≥ fallback (within 0.05), got RAG={macro['rag']}, FB={macro['fallback']}"
    )
