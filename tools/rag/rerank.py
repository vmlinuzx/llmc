from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple
import math
import re


@dataclass
class RerankHit:
    """Intermediate hit used by the reranker, based on DB FTS output."""

    file: str
    start_line: int
    end_line: int
    text: str
    score: float  # raw bm25 (lower is better) or 0.0 if unavailable


_WORD = re.compile(r"[A-Za-z0-9_]+")


def _tokens(s: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(s or "") if len(t) > 1]


def _bigrams(tokens: List[str]) -> List[Tuple[str, str]]:
    return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)] if len(tokens) > 1 else []


def _jaccard(a: Iterable, b: Iterable) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb) or 1
    return inter / union


def _presence(substr: str, text: str) -> float:
    if not substr:
        return 0.0
    return 1.0 if substr.lower() in (text or "").lower() else 0.0


def _normalize_bm25(raw: float) -> float:
    """Normalize raw bm25 (lower-is-better) into [0,1] with higher better."""
    try:
        r = float(raw)
        if not math.isfinite(r) or r < 0:
            r = 0.0 if not math.isfinite(r) else max(0.0, r)
    except Exception:
        r = 0.0
    return 1.0 / (1.0 + r)


def rerank_hits(query: str, hits: List[RerankHit], top_k: int = 20) -> List[RerankHit]:
    """Combine bm25 and token-overlap signals to rerank FTS hits."""
    q_tokens = _tokens(query)
    q_bigrams = _bigrams(q_tokens)
    joined = " ".join(q_tokens)

    rescored: List[Tuple[float, RerankHit]] = []
    for h in hits:
        t = h.text[:1500]
        h_tokens = _tokens(t)
        h_bigrams = _bigrams(h_tokens)

        s_bm25 = _normalize_bm25(h.score) if h.score is not None else 0.0
        s_uni = _jaccard(q_tokens, h_tokens)
        s_bi = _jaccard(q_bigrams, h_bigrams)
        s_lit = _presence(joined, t)
        s_path = _jaccard(q_tokens, _tokens(h.file))

        score = (0.60 * s_bm25) + (0.20 * s_uni) + (0.15 * s_bi) + (0.03 * s_path) + (0.02 * s_lit)
        rescored.append((score, h))

    rescored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in rescored[:top_k]]

