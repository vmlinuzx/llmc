from __future__ import annotations

import functools
import hashlib
import logging
import struct
import time
from dataclasses import dataclass
from typing import List, Tuple
from collections.abc import Iterable, Sequence

from .config import (
    embedding_device_preference,
    embedding_gpu_max_retries,
    embedding_gpu_min_free_mb,
    embedding_gpu_retry_seconds,
    embedding_model_dim,
    embedding_model_name,
    embedding_model_preset,
    embedding_normalize,
    embedding_passage_prefix,
    embedding_query_prefix,
    embedding_wait_for_gpu,
)

HASH_MODELS = {"hash-emb-v1", "hash", "deterministic"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingSpec:
    model_name: str
    dim: int
    passage_prefix: str
    query_prefix: str
    normalize: bool


def _load_sentence_transformer(model_name: str, device: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - dependency resolution
        raise RuntimeError(
            "sentence-transformers is required for embedding generation. "
            "Install it via `pip install sentence-transformers`."
        ) from exc

    @functools.lru_cache(maxsize=4)
    def _loader(name: str, dev: str) -> SentenceTransformer:
        model = SentenceTransformer(name, device=dev)
        return model

    return _loader(model_name, device)


def _select_device() -> Tuple[str, str | None]:
    pref = embedding_device_preference()
    pref = pref.strip().lower()

    if pref == "cpu":
        return "cpu", None

    try:
        import torch
    except ImportError:
        return "cpu", "embedding backend: torch not available; using CPU"

    if not torch.cuda.is_available():
        return "cpu", "embedding backend: CUDA unavailable; using CPU"

    # Determine target GPU index
    device_index = 0
    explicit_index = False
    if pref.startswith("cuda:"):
        explicit_index = True
        try:
            device_index = int(pref.split(":", 1)[1])
        except ValueError:
            device_index = 0
    elif pref in {"cuda", "gpu"}:
        explicit_index = True
        device_index = 0

    guard_enabled = embedding_wait_for_gpu()
    min_free_mb = embedding_gpu_min_free_mb()
    min_free_bytes = max(0, min_free_mb) * 1024 * 1024
    retries = embedding_gpu_max_retries() if guard_enabled else 0
    retry_delay = embedding_gpu_retry_seconds()

    def device_label() -> str:
        if explicit_index or device_index != 0:
            return f"cuda:{device_index}"
        return "cuda"

    last_free_bytes = None

    for attempt in range(retries + 1):
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info(device_index)
            last_free_bytes = free_bytes
        except Exception as exc:  # pragma: no cover - defensive guard
            return "cpu", f"embedding backend: unable to inspect GPU memory ({exc}); falling back to CPU"

        if free_bytes >= min_free_bytes:
            if attempt > 0:
                waited = attempt * retry_delay
                return device_label(), f"embedding backend: GPU free after waiting {waited}s; using {device_label()}"
            return device_label(), None

        if retries == 0:
            break
        if attempt < retries:
            time.sleep(retry_delay)

    if min_free_bytes == 0:
        return device_label(), None

    if last_free_bytes is None:
        return "cpu", "embedding backend: unable to read GPU memory; using CPU"

    free_mb = last_free_bytes / (1024 * 1024)
    message = (
        f"embedding backend: GPU busy (free={free_mb:.0f} MiB < {min_free_mb} MiB); "
        "falling back to CPU"
    )
    return "cpu", message


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
        self._device, notice = _select_device()
        if notice:
            logger.info(notice)
        self._model = _load_sentence_transformer(spec.model_name, self._device)
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
    if model_name is None:
        preset = embedding_model_preset()
        logger.debug("embedding backend using preset %s (%s)", preset, resolved_model)
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
        passage_prefix=passage_prefix if passage_prefix is not None else embedding_passage_prefix(),
        query_prefix=query_prefix if query_prefix is not None else embedding_query_prefix(),
        normalize=resolved_normalize,
    )
    return SentenceTransformerBackend(spec)
