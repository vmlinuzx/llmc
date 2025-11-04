from __future__ import annotations

import functools
import hashlib
import struct
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .config import (
    embedding_model_dim,
    embedding_model_name,
    embedding_normalize,
    embedding_passage_prefix,
    embedding_query_prefix,
)

HASH_MODELS = {"hash-emb-v1", "hash", "deterministic"}


@dataclass(frozen=True)
class EmbeddingSpec:
    model_name: str
    dim: int
    passage_prefix: str
    query_prefix: str
    normalize: bool


def _lru_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - dependency resolution
        raise RuntimeError(
            "sentence-transformers is required for embedding generation. "
            "Install it via `pip install sentence-transformers`."
        ) from exc

    @functools.lru_cache(maxsize=4)
    def _loader(name: str) -> SentenceTransformer:
        model = SentenceTransformer(name)
        return model

    return _loader(model_name)


def _deterministic_embedding(payload: bytes, dim: int) -> List[float]:
    """Hash-based embedding placeholder to keep the worker deterministic/offline."""
    values: List[float] = []
    seed = payload
    while len(values) < dim:
        digest = hashlib.sha256(seed).digest()
        seed = digest  # next round
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                continue
            val = struct.unpack("<I", chunk)[0]
            # map integer to [-1, 1]
            values.append((val / 0xFFFFFFFF) * 2 - 1)
            if len(values) == dim:
                break
    return values


class EmbeddingBackend:
    def __init__(self, spec: EmbeddingSpec):
        self.spec = spec

    @property
    def model_name(self) -> str:
        return self.spec.model_name

    @property
    def dim(self) -> int:
        return self.spec.dim

    def embed_passages(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError

    def format_passages(self, raw_texts: Iterable[str]) -> List[str]:
        prefix = self.spec.passage_prefix
        formatted: List[str] = []
        for text in raw_texts:
            stripped = text.strip()
            if prefix:
                formatted.append(f"{prefix}{stripped}")
            else:
                formatted.append(stripped)
        return formatted

    def format_queries(self, raw_texts: Iterable[str]) -> List[str]:
        prefix = self.spec.query_prefix
        formatted: List[str] = []
        for text in raw_texts:
            stripped = text.strip()
            if prefix:
                formatted.append(f"{prefix}{stripped}")
            else:
                formatted.append(stripped)
        return formatted


class HashEmbeddingBackend(EmbeddingBackend):
    def __init__(self, spec: EmbeddingSpec):
        super().__init__(spec)

    def _encode(self, texts: Sequence[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            payload = text.encode("utf-8", errors="ignore")
            vectors.append(_deterministic_embedding(payload, self.dim))
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> List[List[float]]:
        formatted = self.format_passages(texts)
        return self._encode(formatted)

    def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        formatted = self.format_queries(texts)
        return self._encode(formatted)


class SentenceTransformerBackend(EmbeddingBackend):
    def __init__(self, spec: EmbeddingSpec):
        super().__init__(spec)
        self._model = _lru_sentence_transformer(spec.model_name)
        dimension = getattr(self._model, "get_sentence_embedding_dimension", lambda: None)()
        if isinstance(dimension, int) and dimension > 0:
            self.spec = EmbeddingSpec(
                model_name=spec.model_name,
                dim=dimension,
                passage_prefix=spec.passage_prefix,
                query_prefix=spec.query_prefix,
                normalize=spec.normalize,
            )

    def _encode(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=self.spec.normalize,
            batch_size=max(1, min(32, len(texts))),
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_passages(self, texts: Sequence[str]) -> List[List[float]]:
        formatted = self.format_passages(texts)
        return self._encode(formatted)

    def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        formatted = self.format_queries(texts)
        return self._encode(formatted)


def build_embedding_backend(
    model_name: str | None = None,
    *,
    dim: int | None = None,
    passage_prefix: str | None = None,
    query_prefix: str | None = None,
    normalize: bool | None = None,
) -> EmbeddingBackend:
    resolved_model = model_name or embedding_model_name()
    resolved_normalize = normalize if normalize is not None else embedding_normalize()

    if resolved_model in HASH_MODELS:
        resolved_dim = dim if dim is not None else 64
        spec = EmbeddingSpec(
            model_name=resolved_model,
            dim=resolved_dim,
            passage_prefix=passage_prefix or "",
            query_prefix=query_prefix or "",
            normalize=resolved_normalize,
        )
        return HashEmbeddingBackend(spec)

    resolved_dim = dim if dim is not None else embedding_model_dim()
    spec = EmbeddingSpec(
        model_name=resolved_model,
        dim=resolved_dim,
        passage_prefix=passage_prefix or embedding_passage_prefix(),
        query_prefix=query_prefix or embedding_query_prefix(),
        normalize=resolved_normalize,
    )
    return SentenceTransformerBackend(spec)
