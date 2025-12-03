from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import hashlib
import logging
import math

from .config import (
    embedding_model_dim,
    embedding_model_name,
    embedding_normalize,
    embedding_passage_prefix,
    embedding_query_prefix,
)
from .embedding_manager import EmbeddingManager

logger = logging.getLogger(__name__)

# Logical model names that should use the cheap, deterministic hash backend
HASH_MODELS: set[str] = {"hash-emb-v1"}


@dataclass(frozen=True)
class EmbeddingSpec:
    """Describes the active embedding space.

    This is primarily used for metadata (DB records, tests) and for the
    hash backend where we fully control the embedding space shape.
    """

    model_name: str
    dim: int
    passage_prefix: str
    query_prefix: str
    normalize: bool


# ---------------------------------------------------------------------------
# Hash backend (pure Python, deterministic; great for tests / cheap runs)
# ---------------------------------------------------------------------------


def _hash_to_vector(text: str, dim: int) -> list[float]:
    """Map text deterministically to a vector in [-1, 1]^dim.

    This is intentionally simple and fast, not statistically pretty.
    """
    if dim <= 0:
        raise ValueError("dimension must be positive")

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = bytearray()
    # We need 2 bytes per dimension to get a 16-bit value
    needed_bytes = dim * 2

    while len(raw) < needed_bytes:
        raw.extend(digest)
        digest = hashlib.sha256(digest).digest()

    vals: list[float] = []
    for i in range(dim):
        hi = raw[2 * i]
        lo = raw[2 * i + 1]
        v = ((hi << 8) | lo) / 65535.0 * 2.0 - 1.0
        vals.append(float(v))
    return vals


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    inv = 1.0 / norm
    return [v * inv for v in vec]


class HashEmbeddingBackend:
    """Deterministic hash-based embeddings.

    Used for tests and ultra-cheap smoke runs. It implements the same
    surface as the real backends that workers/search expect:
    - model_name, dim
    - format_passages / format_queries
    - embed_passages / embed_queries
    """

    def __init__(self, spec: EmbeddingSpec) -> None:
        self._spec = spec

    # --- Metadata -----------------------------------------------------
    @property
    def model_name(self) -> str:
        return self._spec.model_name

    @property
    def dim(self) -> int:
        return self._spec.dim

    # --- Formatting ---------------------------------------------------
    def format_passages(self, raw_texts: Iterable[str]) -> list[str]:
        prefix = self._spec.passage_prefix or ""
        return [f"{prefix}{text.strip()}" for text in raw_texts]

    def format_queries(self, raw_texts: Iterable[str]) -> list[str]:
        prefix = self._spec.query_prefix or ""
        return [f"{prefix}{text.strip()}" for text in raw_texts]

    # --- Embedding ----------------------------------------------------
    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        dim = self._spec.dim
        normalize = self._spec.normalize
        vectors: list[list[float]] = []
        for text in texts:
            vec = _hash_to_vector(text, dim)
            if normalize:
                vec = _l2_normalize(vec)
            vectors.append(vec)
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        formatted = self.format_passages(texts)
        return self._embed(formatted)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        formatted = self.format_queries(texts)
        return self._embed(formatted)


# ---------------------------------------------------------------------------
# Manager-backed backend (real models: SentenceTransformers, Ollama, ...)
# ---------------------------------------------------------------------------


class ManagerEmbeddingBackend:
    """Thin adapter around EmbeddingManager for non-hash models.

    This keeps the legacy backend-style surface used by workers, search,
    and benchmark, while delegating the actual vector work to the new
    EmbeddingManager + EmbeddingProvider stack.
    """

    def __init__(self, model_name: str, dim: int) -> None:
        self._model_name = model_name
        self._dim = dim

    # --- Metadata -----------------------------------------------------
    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    # --- Helpers ------------------------------------------------------
    @staticmethod
    def _manager() -> EmbeddingManager:
        return EmbeddingManager.get()

    def format_passages(self, raw_texts: Iterable[str]) -> list[str]:
        prefix = embedding_passage_prefix()
        return [f"{prefix}{text.strip()}" for text in raw_texts]

    def format_queries(self, raw_texts: Iterable[str]) -> list[str]:
        prefix = embedding_query_prefix()
        return [f"{prefix}{text.strip()}" for text in raw_texts]

    # --- Embedding ----------------------------------------------------
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        formatted = self.format_passages(texts)
        return self._manager().embed_passages(formatted)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        formatted = self.format_queries(texts)
        return self._manager().embed_queries(formatted)


# ---------------------------------------------------------------------------
# Public factory + helper functions
# ---------------------------------------------------------------------------


def build_embedding_backend(
    model_override: str | None = None,
    *,
    dim: int | None = None,
) -> HashEmbeddingBackend | ManagerEmbeddingBackend:
    """Factory used by workers/search/benchmark.

    - If model_override (or the configured model) is one of HASH_MODELS,
      return a HashEmbeddingBackend.
    - Otherwise, return a ManagerEmbeddingBackend that delegates to the
      configured EmbeddingManager profile.
    """
    model_name = model_override or embedding_model_name()
    normalize = embedding_normalize()
    passage_prefix = embedding_passage_prefix()
    query_prefix = embedding_query_prefix()

    if model_name in HASH_MODELS:
        effective_dim = dim or embedding_model_dim() or 64
        spec = EmbeddingSpec(
            model_name=model_name,
            dim=effective_dim,
            passage_prefix=passage_prefix,
            query_prefix=query_prefix,
            normalize=normalize,
        )
        logger.info(
            "Using HashEmbeddingBackend(model=%s, dim=%d)",
            spec.model_name,
            spec.dim,
        )
        return HashEmbeddingBackend(spec)

    # Non-hash model: go through the manager / providers
    effective_dim = dim or embedding_model_dim()
    logger.info(
        "Using ManagerEmbeddingBackend(model=%s, dim=%d)",
        model_name,
        effective_dim,
    )
    return ManagerEmbeddingBackend(model_name, effective_dim)


# Convenience helpers for simple callers -----------------------------------


def embedding_model_spec() -> EmbeddingSpec:
    """Return the EmbeddingSpec for the current configuration.

    This is mostly kept for backwards compatibility and debugging.
    """
    return EmbeddingSpec(
        model_name=embedding_model_name(),
        dim=embedding_model_dim(),
        passage_prefix=embedding_passage_prefix(),
        query_prefix=embedding_query_prefix(),
        normalize=embedding_normalize(),
    )


def generate_embeddings(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Backwards-compatible helper to get embeddings for a batch of texts."""
    backend = build_embedding_backend()
    if is_query:
        return backend.embed_queries(texts)
    return backend.embed_passages(texts)


def embed_passages(texts: Sequence[str]) -> list[list[float]]:
    """Embed passages using the currently configured backend."""
    backend = build_embedding_backend()
    return backend.embed_passages(list(texts))


def embed_queries(texts: Sequence[str]) -> list[list[float]]:
    """Embed queries using the currently configured backend."""
    backend = build_embedding_backend()
    return backend.embed_queries(list(texts))
