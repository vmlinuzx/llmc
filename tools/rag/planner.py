from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .database import Database

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "with",
    "is",
    "are",
    "do",
    "does",
    "how",
    "what",
    "where",
    "when",
    "why",
    "who",
    "we",
    "please",
}


@dataclass
class SpanCandidate:
    span_hash: str
    path: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    summary: str
    inputs: Sequence[str]
    outputs: Sequence[str]
    side_effects: Sequence[str]
    pitfalls: Sequence[str]
    usage_snippet: Optional[str]


@dataclass
class PlanSpan:
    span_hash: str
    path: str
    lines: Tuple[int, int]
    score: float
    rationale: Sequence[str]
    symbol: str


@dataclass
class PlanResult:
    query: str
    intent: str
    spans: Sequence[PlanSpan]
    symbols: Sequence[Dict[str, object]]
    confidence: float
    fallback_recommended: bool
    rationale: Sequence[str]


def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for raw in TOKEN_PATTERN.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        tokens.append(raw)
    return tokens


def _derive_intent(tokens: Sequence[str]) -> str:
    if not tokens:
        return "general_query"
    return "-".join(tokens[:4])


def _load_json_field(raw: Optional[str]) -> Sequence[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, (str, int, float))]
    return []


def _fetch_candidates(db: Database) -> Iterable[SpanCandidate]:
    rows = db.conn.execute(
        """
        SELECT spans.span_hash,
               spans.symbol,
               spans.kind,
               spans.start_line,
               spans.end_line,
               files.path,
               COALESCE(enrichments.summary, '') AS summary,
               enrichments.inputs,
               enrichments.outputs,
               enrichments.side_effects,
               enrichments.pitfalls,
               enrichments.usage_snippet
        FROM spans
        JOIN files ON spans.file_id = files.id
        LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
        """
    ).fetchall()
    for row in rows:
        yield SpanCandidate(
            span_hash=row["span_hash"],
            path=row["path"],
            symbol=row["symbol"],
            kind=row["kind"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            summary=row["summary"] or "",
            inputs=_load_json_field(row["inputs"]),
            outputs=_load_json_field(row["outputs"]),
            side_effects=_load_json_field(row["side_effects"]),
            pitfalls=_load_json_field(row["pitfalls"]),
            usage_snippet=row["usage_snippet"],
        )


def _score_candidate(tokens: Sequence[str], candidate: SpanCandidate) -> Tuple[float, List[str]]:
    if not tokens:
        return 0.0, []

    path_l = candidate.path.lower()
    symbol_l = candidate.symbol.lower()
    summary_l = candidate.summary.lower()
    inputs_l = " ".join(candidate.inputs).lower()
    outputs_l = " ".join(candidate.outputs).lower()
    side_effects_l = " ".join(candidate.side_effects).lower()
    pitfalls_l = " ".join(candidate.pitfalls).lower()
    usage_l = (candidate.usage_snippet or "").lower()

    score = 0.0
    reasons: List[str] = []

    def bump(reason: str, weight: float) -> None:
        nonlocal score
        score += weight
        reasons.append(reason)

    matched_tokens = set()
    for token in tokens:
        if token in matched_tokens:
            continue
        token_present = False
        if token in symbol_l:
            bump(f"symbol '{candidate.symbol}' matches '{token}'", 3.0)
            token_present = True
        if token in path_l:
            bump(f"path '{candidate.path}' contains '{token}'", 2.5)
            token_present = True
        if token in summary_l:
            bump(f"summary mentions '{token}'", 1.8)
            token_present = True
        if token in inputs_l:
            bump(f"inputs reference '{token}'", 1.5)
            token_present = True
        if token in outputs_l:
            bump(f"outputs reference '{token}'", 1.2)
            token_present = True
        if token in side_effects_l:
            bump(f"side effects mention '{token}'", 1.0)
            token_present = True
        if token in pitfalls_l:
            bump(f"pitfalls mention '{token}'", 0.9)
            token_present = True
        if token in usage_l:
            bump("usage snippet includes query token", 0.6)
            token_present = True

        if token_present:
            matched_tokens.add(token)

    if candidate.summary:
        score += 0.5

    return score, reasons


def _score_to_confidence(score: float) -> float:
    if score <= 0:
        return 0.0
    return min(0.99, score / (score + 4.0))


def _append_plan_log(repo_root: Path, payload: Dict[str, object]) -> None:
    log_path = repo_root / "logs" / "planner_metrics.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")


def _resolve_repo_root() -> Path:
    cur = Path.cwd()
    for candidate in [cur] + list(cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return cur


def generate_plan(
    query: str,
    limit: int = 5,
    min_score: float = 0.4,
    min_confidence: float = 0.6,
    repo_root: Optional[Path] = None,
    log: bool = True,
) -> PlanResult:
    repo_root = repo_root or _resolve_repo_root()
    db = Database(repo_root / ".rag" / "index.db")
    try:
        tokens = _tokenize(query)
        intent = _derive_intent(tokens)
        scored: List[PlanSpan] = []

        for candidate in _fetch_candidates(db):
            score, reasons = _score_candidate(tokens, candidate)
            if score < min_score:
                continue
            scored.append(
                PlanSpan(
                    span_hash=candidate.span_hash,
                    path=candidate.path,
                    lines=(candidate.start_line, candidate.end_line),
                    score=round(score, 3),
                    rationale=reasons[:4],
                    symbol=candidate.symbol,
                )
            )
    finally:
        db.close()

    scored.sort(key=lambda s: s.score, reverse=True)
    selected = scored[:limit]
    top_score = selected[0].score if selected else 0.0
    confidence = round(_score_to_confidence(top_score), 3)
    fallback = confidence < min_confidence or not selected

    symbols = []
    seen_symbols = set()
    for span in selected:
        if span.symbol in seen_symbols:
            continue
        symbols.append(
            {
                "name": span.symbol,
                "path": span.path,
                "score": span.score,
            }
        )
        seen_symbols.add(span.symbol)
        if len(symbols) >= limit:
            break

    rationale: List[str] = []
    if selected:
        rationale.extend(selected[0].rationale)
    if fallback:
        rationale.append("confidence below threshold; include broader fallback context.")

    plan = PlanResult(
        query=query,
        intent=intent,
        spans=selected,
        symbols=symbols,
        confidence=confidence,
        fallback_recommended=fallback,
        rationale=rationale[:5],
    )

    if log:
        _append_plan_log(
            repo_root,
            {
                "query": query,
                "intent": intent,
                "confidence": confidence,
                "span_count": len(selected),
                "fallback": fallback,
                "top_span": asdict(selected[0]) if selected else None,
            },
        )

    return plan


def plan_as_dict(result: PlanResult) -> Dict[str, object]:
    return {
        "query": result.query,
        "intent": result.intent,
        "symbols": result.symbols,
        "spans": [
            {
                "span_hash": span.span_hash,
                "path": span.path,
                "lines": list(span.lines),
                "score": span.score,
                "rationale": list(span.rationale),
            }
            for span in result.spans
        ],
        "confidence": result.confidence,
        "fallback_recommended": result.fallback_recommended,
        "rationale": list(result.rationale),
    }
