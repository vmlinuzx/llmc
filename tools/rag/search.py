from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from .config import index_path_for_read
from .database import Database
from .embeddings import build_embedding_backend
from .utils import find_repo_root


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _unpack_vector(blob: bytes) -> List[float]:
    dim = len(blob) // 4
    return list(struct.unpack(f"<{dim}f", blob))


@dataclass(frozen=True)
class SpanSearchResult:
    span_hash: str
    path: Path
    symbol: str
    kind: str
    start_line: int
    end_line: int
    score: float
    summary: str | None


def _score_candidates(
    query_vector: Sequence[float],
    query_norm: float,
    rows: Iterable,
) -> List[SpanSearchResult]:
    results: List[SpanSearchResult] = []
    for row in rows:
        vector = _unpack_vector(row["vec"])
        vector_norm = _norm(vector)
        if query_norm == 0.0 or vector_norm == 0.0:
            continue
        similarity = _dot(query_vector, vector) / (query_norm * vector_norm)
        results.append(
            SpanSearchResult(
                span_hash=row["span_hash"],
                path=Path(row["file_path"]),
                symbol=row["symbol"],
                kind=row["kind"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                score=float(similarity),
                summary=row["summary"] or None,
            )
        )
    results.sort(key=lambda item: item.score, reverse=True)
    return results


def search_spans(
    query: str,
    *,
    limit: int = 5,
    repo_root: Path | None = None,
    model_override: str | None = None,
) -> List[SpanSearchResult]:
    """Execute a simple cosine-similarity search over the local `.rag` index."""
    repo = repo_root or find_repo_root()
    db_path = index_path_for_read(repo)
    if not db_path.exists():
        raise FileNotFoundError(
            f"No embedding index found at {db_path}. Run `python -m tools.rag.cli index` and `embed --execute` first."
        )

    backend = build_embedding_backend(model_override)
    query_vector = backend.embed_queries([query])[0]
    query_norm = _norm(query_vector)

    db = Database(db_path)
    try:
        scored = _score_candidates(query_vector, query_norm, db.iter_embeddings())
    finally:
        db.close()
    return scored[:limit]

