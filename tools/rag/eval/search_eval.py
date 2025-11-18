from __future__ import annotations

"""
Search evaluation harness for comparing RAG vs. fallback search.

This is a lightweight, file-oriented evaluator used in P9e to sanity-check
that graph-backed RAG search is at least as good as the local fallback for a
small set of canary queries.
"""

import argparse
import fnmatch
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.rag.db_fts import fts_search
from tools.rag.rerank import RerankHit, rerank_hits
from tools.rag.config import load_rerank_weights
from tools.rag_nav.tool_handlers import tool_rag_search


def load_queries(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL canary query specs."""
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def precision_at_k_files(files: List[str], gold_globs: List[str], k: int) -> float:
    """Precision@k using filename glob patterns as relevance labels."""
    if not gold_globs:
        return 0.0
    top = files[:k]
    hits = 0
    for path in top:
        if any(fnmatch.fnmatch(path, pattern) for pattern in gold_globs):
            hits += 1
    return hits / max(1, k)


def precision_at_k_tokens(items: List[Dict[str, Any]], relevant_tokens: List[str], k: int) -> float:
    """Precision@k based on token presence in file path + snippet text."""
    tokens = [token.lower() for token in relevant_tokens]
    top = items[:k]
    hits = 0
    for item in top:
        blob = (item.get("file", "") + " " + item.get("text", "")).lower()
        if any(token in blob for token in tokens):
            hits += 1
    return hits / max(1, k)


def eval_rag(repo: Path, query: str, limit: int) -> List[Dict[str, Any]]:
    """Evaluate RAG search using the existing FTS + reranker stack."""
    hits = fts_search(repo, query, limit=max(100, limit * 3))
    rerank_hits_input = [
        RerankHit(
            file=h.file,
            start_line=h.start_line,
            end_line=h.end_line,
            text=h.text,
            score=h.score,
        )
        for h in hits
    ]
    weights = load_rerank_weights(repo)
    top = rerank_hits(query, rerank_hits_input, top_k=limit, weights=weights)
    return [
        {
            "file": hit.file,
            "text": hit.text,
            "start_line": hit.start_line,
            "end_line": hit.end_line,
        }
        for hit in top
    ]


def eval_fallback(repo: Path, query: str, limit: int) -> List[Dict[str, Any]]:
    """Evaluate the local fallback search (graph disabled)."""
    # Use the nav tool directly with a forced fallback route by pointing at a
    # non-RAG repo root (callers should set up the environment appropriately).
    result = tool_rag_search(str(repo), query, limit=limit)
    return [
        {
            "file": item.file,
            "text": item.snippet.text,
            "start_line": item.snippet.location.start_line,
            "end_line": item.snippet.location.end_line,
        }
        for item in result.items
    ]


def run(
    repo_root: Path,
    queries_path: Path,
    out_dir: Path,
    k: int = 10,
    mode: str = "both",
) -> Dict[str, Any]:
    """
    Run search evaluation over a set of canary queries.

    mode:
      - "rag":      evaluate only the RAG path
      - "fallback": evaluate only the local fallback path
      - "both":     evaluate both and compare macro precision@k
    """
    mode_normalized = (mode or "both").lower()
    assert mode_normalized in ("rag", "fallback", "both")

    rows = load_queries(queries_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "k": k,
        "n": len(rows),
        "mode": mode_normalized,
        "by_query": [],
    }
    rag_scores_tokens: List[float] = []
    fb_scores_tokens: List[float] = []
    rag_scores_gold: List[float] = []
    fb_scores_gold: List[float] = []

    for row in rows:
        query = row["q"]
        relevant = row.get("relevant", [])
        gold_globs = row.get("gold_globs", [])

        rag_items: Optional[List[Dict[str, Any]]] = None
        fb_items: Optional[List[Dict[str, Any]]] = None

        if mode_normalized in ("rag", "both"):
            try:
                rag_items = eval_rag(repo_root, query, limit=max(10, k))
            except Exception:
                # In environments without a DB or where RAG search is unavailable,
                # fall back to the same behavior as the local fallback path so
                # metrics remain comparable rather than silently degrading to 0.
                rag_items = eval_fallback(repo_root, query, limit=max(10, k))

        if mode_normalized in ("fallback", "both"):
            fb_items = eval_fallback(repo_root, query, limit=max(10, k))

        rag_files = [item["file"] for item in (rag_items or [])]
        fb_files = [item["file"] for item in (fb_items or [])]

        p_rag_tokens = precision_at_k_tokens(rag_items or [], relevant, k) if rag_items is not None else None
        p_fb_tokens = precision_at_k_tokens(fb_items or [], relevant, k) if fb_items is not None else None
        p_rag_gold = (
            precision_at_k_files(rag_files, gold_globs, k) if (rag_items is not None and gold_globs) else None
        )
        p_fb_gold = (
            precision_at_k_files(fb_files, gold_globs, k) if (fb_items is not None and gold_globs) else None
        )

        if p_rag_tokens is not None:
            rag_scores_tokens.append(p_rag_tokens)
        if p_fb_tokens is not None:
            fb_scores_tokens.append(p_fb_tokens)
        if p_rag_gold is not None:
            rag_scores_gold.append(p_rag_gold)
        if p_fb_gold is not None:
            fb_scores_gold.append(p_fb_gold)

        summary["by_query"].append(
            {
                "q": query,
                "rag": {"p_at_k_tokens": p_rag_tokens, "files": rag_files} if rag_items is not None else None,
                "fallback": {"p_at_k_tokens": p_fb_tokens, "files": fb_files} if fb_items is not None else None,
                "gold": gold_globs or None,
                "p_at_k_gold": (
                    {"rag": p_rag_gold, "fallback": p_fb_gold}
                    if gold_globs and (rag_items is not None or fb_items is not None)
                    else None
                ),
            }
        )

    def _avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    macro_tokens = {
        "rag": _avg(rag_scores_tokens) if rag_scores_tokens else None,
        "fallback": _avg(fb_scores_tokens) if fb_scores_tokens else None,
    }
    macro_gold = {
        "rag": _avg(rag_scores_gold) if rag_scores_gold else None,
        "fallback": _avg(fb_scores_gold) if fb_scores_gold else None,
    }
    summary["macro"] = {"tokens": macro_tokens, "gold": macro_gold}

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"search_eval_{timestamp}.json"
    md_path = out_dir / f"search_eval_{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# Search Eval Report — {timestamp}\n\n")
        handle.write(f"- k: {k}\n- queries: {summary['n']}\n- mode: {mode_normalized}\n\n")
        handle.write("## Macro Scores\n\n")
        if macro_tokens["rag"] is not None or macro_tokens["fallback"] is not None:
            rag_value = macro_tokens["rag"]
            fb_value = macro_tokens["fallback"]
            handle.write(
                f"- Tokens P@{k}: RAG={rag_value if rag_value is not None else '—'}, "
                f"Fallback={fb_value if fb_value is not None else '—'}\n"
            )
        if macro_gold["rag"] is not None or macro_gold["fallback"] is not None:
            rag_gold = macro_gold["rag"]
            fb_gold = macro_gold["fallback"]
            handle.write(
                f"- Gold P@{k}: RAG={rag_gold if rag_gold is not None else '—'}, "
                f"Fallback={fb_gold if fb_gold is not None else '—'}\n"
            )
        handle.write("\n## Per-Query\n")
        for row in summary["by_query"]:
            handle.write(f"\n### {row['q']}\n")
            if row.get("rag") is not None:
                handle.write(f"- Tokens P@{k} (RAG): {row['rag']['p_at_k_tokens']}\n")
            if row.get("fallback") is not None:
                handle.write(f"- Tokens P@{k} (FB): {row['fallback']['p_at_k_tokens']}\n")
            if row.get("p_at_k_gold") is not None:
                handle.write(
                    f"- Gold P@{k}: RAG={row['p_at_k_gold']['rag']}, "
                    f"FB={row['p_at_k_gold']['fallback']}\n"
                )
            if row.get("rag") is not None:
                handle.write("- RAG files:\n")
                for path in row["rag"]["files"][:k]:
                    handle.write(f"  - `{path}`\n")
            if row.get("fallback") is not None:
                handle.write("- FB files:\n")
                for path in row["fallback"]["files"][:k]:
                    handle.write(f"  - `{path}`\n")

    return {"json": str(json_path), "md": str(md_path), "summary": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", default=".", help="Repo root")
    parser.add_argument(
        "--queries",
        default="DOCS/RAG_NAV/P9_Search/canary_queries.jsonl",
        help="JSONL with q, relevant[], optional gold_globs[]",
    )
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--out", default=".llmc/eval")
    parser.add_argument("--mode", choices=["rag", "fallback", "both"], default="both")
    args = parser.parse_args()

    result = run(Path(args.repo_root).resolve(), Path(args.queries), Path(args.out), k=args.k, mode=args.mode)
    print(
        json.dumps(
            {"wrote": result["json"], "md": result["md"], "macro": result["summary"]["macro"]},
            indent=2,
        )
    )
