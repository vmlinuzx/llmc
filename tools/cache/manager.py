from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from . import config
from .database import CacheDatabase
from tools.rag.embeddings import build_embedding_backend


@dataclass
class CacheEntry:
    id: int
    prompt_hash: str
    route: str
    provider: Optional[str]
    prompt: str
    user_prompt: Optional[str]
    response: str
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    total_cost: Optional[float]
    created_at: str
    score: float


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _unpack_vector(blob: bytes, dim: int) -> Iterable[float]:
    import struct

    pattern = f"<{dim}f"
    return struct.unpack(pattern, blob)


def _cosine_similarity(vec_a: Iterable[float], norm_a: float, vec_b: Iterable[float], norm_b: float) -> float:
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
    return dot / (norm_a * norm_b)


def _compute_norm(vector: Iterable[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def _find_repo_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return current


def _resolve_db(repo_root: Optional[Path] = None) -> CacheDatabase:
    repo = _find_repo_root(repo_root)
    path = config.cache_db_path(repo)
    return CacheDatabase(path)


def lookup(
    prompt: str,
    route: str,
    *,
    provider: Optional[str] = None,
    min_score: Optional[float] = None,
    repo_root: Optional[Path] = None,
) -> tuple[bool, Optional[CacheEntry]]:
    if not config.cache_enabled():
        return False, None

    minimum = min_score if min_score is not None else config.cache_min_score()
    repo = _find_repo_root(repo_root)
    db = _resolve_db(repo)
    prompt_hash = _hash_prompt(prompt)
    backend = build_embedding_backend()
    vector = backend.embed_queries([prompt])[0]
    norm = _compute_norm(vector)

    try:
        if norm == 0.0:
            return False, None

        rows = db.conn.execute(
            """
            SELECT
                e.id, e.prompt_hash, e.route, e.provider, e.prompt, e.user_prompt,
                e.response, e.tokens_in, e.tokens_out, e.total_cost, e.created_at,
                v.dim, v.norm AS stored_norm, v.vec
            FROM entries e
            JOIN entry_vectors v ON v.entry_id = e.id
            WHERE e.route = ?
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (route, config.cache_max_results()),
        ).fetchall()

        best: Optional[CacheEntry] = None
        best_score = -1.0

        for row in rows:
            dim = row["dim"]
            vec = _unpack_vector(row["vec"], dim)
            similarity = _cosine_similarity(vector, norm, vec, row["stored_norm"])
            if similarity >= minimum and similarity > best_score:
                best_score = similarity
                best = CacheEntry(
                    id=int(row["id"]),
                    prompt_hash=row["prompt_hash"],
                    route=row["route"],
                    provider=row["provider"],
                    prompt=row["prompt"],
                    user_prompt=row["user_prompt"],
                    response=row["response"],
                    tokens_in=row["tokens_in"],
                    tokens_out=row["tokens_out"],
                    total_cost=row["total_cost"],
                    created_at=row["created_at"],
                    score=similarity,
                )

        if best and best_score >= minimum:
            return True, best
        return False, None
    finally:
        db.close()


def store(
    prompt: str,
    response: str,
    route: str,
    *,
    provider: Optional[str] = None,
    user_prompt: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    total_cost: Optional[float] = None,
    repo_root: Optional[Path] = None,
) -> None:
    if not config.cache_enabled():
        return

    repo = _find_repo_root(repo_root)
    db = _resolve_db(repo)
    prompt_hash = _hash_prompt(prompt)
    backend = build_embedding_backend()
    vector = backend.embed_queries([prompt])[0]
    norm = _compute_norm(vector)

    import struct

    try:
        entry_id = db.upsert_entry(
            prompt_hash,
            route,
            provider,
            prompt,
            user_prompt,
            response,
            tokens_in,
            tokens_out,
            total_cost,
        )
        blob = struct.pack(f"<{len(vector)}f", *vector)
        db.insert_vector(entry_id, len(vector), norm, blob)
    finally:
        db.close()
