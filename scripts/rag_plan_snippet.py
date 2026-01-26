#!/usr/bin/env python3
"""Emit a compact RAG planner snippet for prompt injection."""

from __future__ import annotations

try:
except ImportError:
    pass

import argparse
from pathlib import Path
import sys

from llmc.rag.config import index_path_for_read
from llmc.rag.planner import generate_plan


def load_query(args: argparse.Namespace) -> str:
    if args.query:
        query = " ".join(args.query).strip()
        if query:
            return query
    data = sys.stdin.read().strip()
    return data


def format_plan(plan) -> str:
    lines = []
    lines.append("RAG Retrieval Plan")
    lines.append(f"Intent: {plan.intent} (confidence {plan.confidence:.2f})")

    if not plan.spans:
        lines.append("- No high-confidence spans found; consider broader context.")
    else:
        for span in plan.spans:
            start, end = span.lines
            rationale = "; ".join(span.rationale)
            detail = f"- {span.path}:{start}-{end} • score {span.score:.2f}"
            if rationale:
                detail += f" • {rationale}"
            lines.append(detail)

    if plan.fallback_recommended:
        lines.append("Fallback: confidence below threshold—include extra context.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a RAG planner snippet for inclusion in prompts."
    )
    parser.add_argument(
        "query", nargs="*", help="Natural language question (defaults to stdin)."
    )
    parser.add_argument(
        "--repo",
        dest="repo",
        default=Path.cwd(),
        type=Path,
        help="Repository root containing .rag/.",
    )
    parser.add_argument(
        "--limit", dest="limit", default=5, type=int, help="Max spans to include."
    )
    parser.add_argument(
        "--min-score",
        dest="min_score",
        default=0.4,
        type=float,
        help="Minimum span score to keep.",
    )
    parser.add_argument(
        "--min-confidence",
        dest="min_confidence",
        default=0.6,
        type=float,
        help="Confidence threshold before recommending fallback.",
    )
    parser.add_argument(
        "--no-log",
        dest="no_log",
        action="store_true",
        help="Skip writing planner metrics to disk.",
    )
    args = parser.parse_args()

    query = load_query(args)
    if not query:
        return 0

    repo_root = args.repo.resolve()
    db_path = index_path_for_read(repo_root)
    if not db_path.exists():
        return 0

    try:
        plan = generate_plan(
            query,
            limit=args.limit,
            min_score=args.min_score,
            min_confidence=args.min_confidence,
            repo_root=repo_root,
            log=not args.no_log,
        )
    except Exception as exc:  # pragma: no cover - best effort helper
        print(f"[rag-plan] failed: {exc}", file=sys.stderr)
        return 1

    snippet = format_plan(plan)
    if snippet.strip():
        print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
