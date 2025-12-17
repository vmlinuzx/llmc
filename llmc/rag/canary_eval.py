"""
Minimal canary evaluator for RAG Nav search.

Runs a small set of queries against tool_rag_search and computes a simple
precision@k metric to compare baseline vs. alternative rerank weights.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

from llmc.rag_nav.tool_handlers import tool_rag_search

DEFAULT_CANARY: list[dict[str, Any]] = [
    {"q": "jwt verify", "relevant": ["jwt", "verify", "auth"]},
    {"q": "sqlite fts search", "relevant": ["fts", "sqlite", "db"]},
    {"q": "graph neighbors", "relevant": ["graph", "edge", "calls", "imports"]},
]


def precision_at_k(
    items: list[object], relevant_tokens: list[str], k: int = 10
) -> float:
    """
    Compute precision@k by checking whether any relevant token appears in the
    file path or snippet text of the top-k items.
    """
    tokens = [t.lower() for t in relevant_tokens]
    top = items[:k]
    hits = 0
    for it in top:
        file_value = getattr(it, "file", "")
        try:
            text_value = getattr(getattr(it, "snippet", object()), "text", "")
        except Exception:
            text_value = ""
        blob = f"{file_value} {text_value}".lower()
        if any(token in blob for token in tokens):
            hits += 1
    return hits / max(1, k)


def _load_queries(path: Path | None) -> list[dict[str, Any]]:
    """Load canary queries from a JSONL file, or fall back to DEFAULT_CANARY."""
    if path and path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                return [json.loads(line) for line in handle if line.strip()]
        except Exception:
            # Fall through to defaults on any parse/IO error.
            pass
    return list(DEFAULT_CANARY)


def _clear_weight_env() -> None:
    """Clear rerank weight environment overrides to establish a baseline."""
    for env in [
        "RAG_RERANK_W_BM25",
        "RAG_RERANK_W_UNI",
        "RAG_RERANK_W_BI",
        "RAG_RERANK_W_PATH",
        "RAG_RERANK_W_LIT",
    ]:
        os.environ.pop(env, None)


def run(
    repo_root: Path, queries_path: Path | None = None, k: int = 10
) -> dict[str, Any]:
    """
    Run a baseline and alt evaluation over a set of canary queries.

    The caller is expected to configure any alternative weights via INI or
    environment before invoking this function.
    """
    queries = _load_queries(queries_path)

    def eval_once() -> float:
        scores: list[float] = []
        for query in queries:
            result = tool_rag_search(repo_root, query["q"], limit=max(10, k))
            scores.append(precision_at_k(result.items, query.get("relevant", []), k=k))
        return sum(scores) / max(1, len(scores))

    # Baseline: defaults only.
    _clear_weight_env()
    baseline = eval_once()

    # Alt: respect whatever env/INI the caller configured.
    alt = eval_once()

    return {"p_at_k": {"baseline": baseline, "alt": alt}, "n": len(queries), "k": k}


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".").resolve()
    queries_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    k_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    result = run(root, queries_arg, k_arg)
    print(json.dumps(result, indent=2))
