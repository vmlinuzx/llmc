#!/usr/bin/env python3
"""Emit a RAG planner bundle (plan metadata + indexed span context)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.rag.config import index_path_for_read
from tools.rag.database import Database
from tools.rag.planner import generate_plan, plan_as_dict


# Hard limits to keep RAG context compact for downstream LLM prompts.
DEFAULT_TOTAL_CHAR_LIMIT = 16000
DEFAULT_SPAN_CHAR_LIMIT = 3200


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


def _load_json_field(raw: str | None) -> Sequence[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, (str, int, float))]
    return []


def _load_span_rows(db_path: Path, span_hashes: Iterable[str]):
    span_hashes = [s for s in span_hashes if s]
    if not span_hashes:
        return {}

    db = Database(db_path)
    try:
        placeholders = ",".join("?" for _ in span_hashes)
        query = f"""
            SELECT spans.span_hash,
                   files.path,
                   files.lang,
                   spans.start_line,
                   spans.end_line,
                   enrichments.summary,
                   enrichments.inputs,
                   enrichments.outputs,
                   enrichments.side_effects,
                   enrichments.pitfalls,
                   enrichments.usage_snippet
            FROM spans
            JOIN files ON spans.file_id = files.id
            LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
            WHERE spans.span_hash IN ({placeholders})
        """
        rows = db.conn.execute(query, span_hashes).fetchall()
        return {row["span_hash"]: row for row in rows}
    finally:
        db.close()


def _guess_language_label(path: str) -> str:
    suffix = Path(path).suffix.lower()
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".cs": "csharp",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".ps1": "powershell",
        ".sql": "sql",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".md": "markdown",
        ".txt": "text",
    }
    return mapping.get(suffix, suffix.lstrip(".") or "text")


def _slice_file(repo_root: Path, rel_path: str, start_line: int, end_line: int, char_limit: int | None) -> tuple[str, bool]:
    file_path = (repo_root / rel_path).resolve()
    if not file_path.exists():
        return f"[missing file: {rel_path}]", False

    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            selected: List[str] = []
            for line_no, raw_line in enumerate(handle, start=1):
                if line_no < start_line:
                    continue
                selected.append(raw_line.rstrip("\n"))
                if line_no >= end_line:
                    break
    except OSError as exc:
        return f"[error reading {rel_path}: {exc}]", False

    snippet = "\n".join(selected)
    truncated = False
    if char_limit is not None and char_limit > 0 and len(snippet) > char_limit:
        snippet = snippet[:char_limit].rstrip()
        truncated = True
    return snippet, truncated


def _format_metadata(label: str, values: Sequence[str]) -> str | None:
    items = [v.strip() for v in values if str(v).strip()]
    if not items:
        return None
    return f"{label}: {', '.join(items)}"


def render_context_section(plan_dict: Dict[str, object], repo_root: Path, total_char_limit: int, span_char_limit: int) -> str:
    spans = plan_dict.get("spans") or []
    if not spans:
        return ""

    db_path = index_path_for_read(repo_root)
    span_rows = _load_span_rows(db_path, (span.get("span_hash") for span in spans))

    lines: List[str] = []
    lines.append("Indexed Context")

    remaining_total = None if total_char_limit <= 0 else total_char_limit
    per_span_limit = None if span_char_limit <= 0 else span_char_limit

    for idx, span in enumerate(spans, start=1):
        span_hash = span.get("span_hash")
        row = span_rows.get(span_hash) if span_hash else None
        path = span.get("path") or (row["path"] if row else "unknown")
        start_line, end_line = span.get("lines", [None, None])[:2]
        start_line = int(start_line or (row["start_line"] if row else 1))
        end_line = int(end_line or (row["end_line"] if row else start_line))
        score = span.get("score")
        rationale = span.get("rationale") or []

        lines.append(f"### Context {idx}: {path}:{start_line}-{end_line} (score {score})")
        if rationale:
            wrapped = textwrap.fill("; ".join(str(r) for r in rationale), width=100)
            lines.append(f"Rationale: {wrapped}")

        if row:
            summary_line = row["summary"] or ""
            if summary_line:
                lines.append(f"Summary: {summary_line.strip()}")

            for label, field in (
                ("Inputs", _load_json_field(row["inputs"])),
                ("Outputs", _load_json_field(row["outputs"])),
                ("Side effects", _load_json_field(row["side_effects"])),
                ("Pitfalls", _load_json_field(row["pitfalls"])),
            ):
                formatted = _format_metadata(label, field)
                if formatted:
                    lines.append(formatted)

            usage_snippet = row["usage_snippet"] or ""
            if usage_snippet.strip():
                wrapped_usage = textwrap.fill(usage_snippet.strip(), width=100)
                lines.append(f"Usage: {wrapped_usage}")

        effective_char_limit = per_span_limit
        if remaining_total is not None:
            if effective_char_limit is None:
                effective_char_limit = remaining_total
            else:
                effective_char_limit = min(effective_char_limit, remaining_total)

        snippet, truncated = _slice_file(repo_root, path, start_line, end_line, effective_char_limit)
        fence_lang = _guess_language_label(path)

        lines.append(f"```{fence_lang}")
        lines.append(snippet if snippet else "[empty snippet]")
        lines.append("```")

        consumed = len(snippet)
        if remaining_total is not None:
            remaining_total = max(0, remaining_total - consumed)

        if truncated and effective_char_limit is not None:
            lines.append(f"… truncated after {effective_char_limit} characters to respect span budget")

        lines.append("")

        if remaining_total == 0:
            lines.append("(Additional span context omitted: total RAG context budget reached.)")
            break

    return "\n".join(line for line in lines if line is not None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a RAG planner snippet for inclusion in prompts.")
    parser.add_argument("query", nargs="*", help="Natural language question (defaults to stdin).")
    parser.add_argument("--repo", dest="repo", default=Path.cwd(), type=Path, help="Repository root containing .llmc/.rag/.")
    parser.add_argument("--limit", dest="limit", default=5, type=int, help="Max spans to include.")
    parser.add_argument("--min-score", dest="min_score", default=0.4, type=float, help="Minimum span score to keep.")
    parser.add_argument(
        "--min-confidence",
        dest="min_confidence",
        default=0.6,
        type=float,
        help="Confidence threshold before recommending fallback.",
    )
    parser.add_argument("--no-log", dest="no_log", action="store_true", help="Skip writing planner metrics to disk.")
    parser.add_argument(
        "--total-char-limit",
        dest="total_char_limit",
        default=None,
        type=int,
        help="Maximum characters of aggregated context to emit (overrides env).",
    )
    parser.add_argument(
        "--span-char-limit",
        dest="span_char_limit",
        default=None,
        type=int,
        help="Maximum characters per span snippet (overrides env).",
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

    snippet_lines: List[str] = []
    snippet_lines.append(format_plan(plan))

    plan_dict = plan_as_dict(plan)
    env_total_limit = os.getenv("RAG_PLAN_CONTEXT_CHAR_LIMIT")
    env_span_limit = os.getenv("RAG_PLAN_SPAN_CHAR_LIMIT")
    total_char_limit = (
        args.total_char_limit
        if args.total_char_limit is not None
        else int(env_total_limit) if env_total_limit else DEFAULT_TOTAL_CHAR_LIMIT
    )
    span_char_limit = (
        args.span_char_limit
        if args.span_char_limit is not None
        else int(env_span_limit) if env_span_limit else DEFAULT_SPAN_CHAR_LIMIT
    )

    context_section = render_context_section(plan_dict, repo_root, total_char_limit, span_char_limit)
    if context_section.strip():
        snippet_lines.append("\n" + context_section)

    output = "\n".join(snippet_lines).strip()
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
