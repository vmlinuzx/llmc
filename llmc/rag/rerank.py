from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
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

# Extension-based scoring
# TODO: Needs proper research - see ROADMAP
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".rs",
    ".go",
    ".c",
    ".cpp",
    ".h",
    ".tsx",
    ".jsx",
    ".vue",
    ".rb",
    ".java",
    ".kt",
    ".swift",
}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}


def _extension_boost(path_str: str) -> float:
    """Return score modifier based on file extension and path."""
    from pathlib import Path

    path_lower = path_str.lower()
    ext = Path(path_str).suffix.lower()

    # Penalize tests - zombie army suppression
    if "test" in path_lower or "/tests/" in path_lower:
        return 0.2  # Heavy penalty for tests

    if ext in CODE_EXTENSIONS:
        return 1.0  # Full weight for code
    if ext in DOC_EXTENSIONS:
        return 0.3  # Reduce doc weight
    return 0.7  # Default for other files


def _tokens(s: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(s or "") if len(t) > 1]


def _bigrams(tokens: list[str]) -> list[tuple[str, str]]:
    return (
        [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]
        if len(tokens) > 1
        else []
    )


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


DEFAULT_WEIGHTS: dict[str, float] = {
    "bm25": 0.55,
    "uni": 0.18,
    "bi": 0.12,
    "path": 0.07,
    "lit": 0.02,
    "ext": 0.06,  # Extension-based boost (code > docs)
}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a weight mapping, falling back to DEFAULT_WEIGHTS if invalid."""
    base = dict(DEFAULT_WEIGHTS)
    if not isinstance(weights, dict) or not weights:
        return base
    total = 0.0
    normalized: dict[str, float] = {}
    for key in base.keys():
        try:
            value = float(weights.get(key, base[key]))
        except Exception:
            value = base[key]
        value = max(0.0, value)
        normalized[key] = value
        total += value
    if total <= 0.0:
        return base
    return {key: value / total for key, value in normalized.items()}


def rerank_hits(
    query: str,
    hits: list[RerankHit],
    top_k: int = 20,
    weights: dict[str, float] | None = None,
) -> list[RerankHit]:
    """Combine bm25 and token-overlap signals to rerank FTS hits."""
    w = _normalize_weights(weights or DEFAULT_WEIGHTS)
    q_tokens = _tokens(query)
    q_bigrams = _bigrams(q_tokens)
    joined = " ".join(q_tokens)

    rescored: list[tuple[float, RerankHit]] = []
    for h in hits:
        t = h.text[:1500]
        h_tokens = _tokens(t)
        h_bigrams = _bigrams(h_tokens)

        s_bm25 = _normalize_bm25(h.score) if h.score is not None else 0.0
        s_uni = _jaccard(q_tokens, h_tokens)
        s_bi = _jaccard(q_bigrams, h_bigrams)
        s_lit = _presence(joined, t)
        s_path = _jaccard(q_tokens, _tokens(h.file))
        s_ext = _extension_boost(h.file)

        score = (
            (w["bm25"] * s_bm25)
            + (w["uni"] * s_uni)
            + (w["bi"] * s_bi)
            + (w["path"] * s_path)
            + (w["lit"] * s_lit)
            + (w["ext"] * s_ext)
        )
        rescored.append((score, h))

    rescored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in rescored[:top_k]]


# =============================================================================
# LLM-BASED SETWISE RERANKING (Phase 4)
# =============================================================================

import json
import logging
from typing import Protocol

logger = logging.getLogger(__name__)

SETWISE_PROMPT = """You are a code retrieval expert.
Query: "{query}"

I will provide candidate snippets. Select those most helpful for answering the query.
* Prefer exact code definitions over usages
* Prefer mechanism documentation over generic intros
* Exclude irrelevant snippets

Candidates:
{candidates}

Output ONLY a JSON list of selected candidate numbers, ordered by relevance.
Example: ["1", "3"]"""


class LLMClient(Protocol):
    """Protocol for LLM clients used in reranking."""

    def generate(self, prompt: str, temperature: float = 0) -> str:
        """Generate text from a prompt."""
        ...


class SetwiseReranker:
    """
    LLM-based setwise reranker.

    Asks the LLM to select the best subset of candidates rather than
    rank all of them, which is more robust to position bias.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        max_candidates: int = 10,
        max_snippet_chars: int = 500,
    ):
        self.llm_client = llm_client
        self.max_candidates = max_candidates
        self.max_snippet_chars = max_snippet_chars

    def _format_candidate(self, idx: int, candidate: dict) -> str:
        """Format a single candidate for the prompt."""
        path = candidate.get("path", candidate.get("slice_id", "unknown"))
        summary = str(candidate.get("summary", ""))[:self.max_snippet_chars]
        symbol = candidate.get("symbol", "")

        return f"[{idx}] {path}\n    Symbol: {symbol}\n    {summary}"

    def _parse_response(self, response: str, num_candidates: int) -> list[int]:
        """Parse LLM response to get selected indices."""
        try:
            # Try to extract JSON array
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end > start:
                selected = json.loads(response[start:end])
                # Convert to 0-indexed integers
                return [int(s) - 1 for s in selected if 0 < int(s) <= num_candidates]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: return original order
        logger.warning("Failed to parse LLM rerank response, using original order")
        return list(range(min(num_candidates, 5)))

    def rerank(
        self,
        query: str,
        candidates: list[dict],
    ) -> list[dict]:
        """
        Rerank candidates using LLM setwise selection.

        Returns reordered candidate list.
        """
        if not candidates:
            return candidates

        if self.llm_client is None:
            logger.debug("No LLM client configured, skipping rerank")
            return candidates

        # Limit candidates
        to_rerank = candidates[: self.max_candidates]
        rest = candidates[self.max_candidates :]

        # Format prompt
        candidates_text = "\n\n".join(
            self._format_candidate(i + 1, c) for i, c in enumerate(to_rerank)
        )

        prompt = SETWISE_PROMPT.format(
            query=query,
            candidates=candidates_text,
        )

        # Call LLM
        try:
            response = self.llm_client.generate(prompt, temperature=0)
            selected_indices = self._parse_response(response, len(to_rerank))
        except Exception as e:
            logger.warning(f"LLM rerank failed: {e}")
            return candidates

        # Reorder based on selection
        reordered = []
        seen: set[int] = set()

        for idx in selected_indices:
            if 0 <= idx < len(to_rerank) and idx not in seen:
                reordered.append(to_rerank[idx])
                seen.add(idx)

        # Add unselected from original top candidates
        for i, c in enumerate(to_rerank):
            if i not in seen:
                reordered.append(c)

        # Add rest
        reordered.extend(rest)

        return reordered


def rerank_with_llm(
    query: str,
    candidates: list[dict],
    config: dict | None = None,
    llm_client: LLMClient | None = None,
) -> list[dict]:
    """
    Convenience function to rerank candidates using LLM.

    Returns original candidates if reranking is disabled or fails.
    """
    if config is None:
        config = {}

    rerank_cfg = config.get("rag", {}).get("rerank", {})

    if not rerank_cfg.get("enable_llm_rerank", False):
        return candidates

    # Check minimum query length
    min_length = rerank_cfg.get("min_query_length", 20)
    if len(query) < min_length:
        logger.debug(f"Query too short for rerank ({len(query)} < {min_length})")
        return candidates

    max_candidates = rerank_cfg.get("max_candidates", 10)
    max_snippet = rerank_cfg.get("max_snippet_chars", 500)

    reranker = SetwiseReranker(
        llm_client=llm_client,
        max_candidates=max_candidates,
        max_snippet_chars=max_snippet,
    )

    return reranker.rerank(query, candidates)

