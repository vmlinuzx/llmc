from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingMetadata:
    """Metadata describing an embedding space/model."""

    provider: str
    model: str
    dimension: int
    profile: str | None = None


class EmbeddingError(Exception):
    """Base exception for embedding-related failures."""


class EmbeddingConfigError(EmbeddingError):
    """Configuration / wiring problem for embeddings."""


class EmbeddingProvider(ABC):
    """Abstract interface for all embedding providers.

    Implementations must be safe for reuse across many calls. Initialization
    is handled by the embedding manager.
    """

    def __init__(self, metadata: EmbeddingMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> EmbeddingMetadata:
        return self._metadata

    @abstractmethod
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed 'document-like' texts for indexing / storage."""

    @abstractmethod
    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed 'query-like' texts for retrieval / search."""

    def close(self) -> None:
        """Optional cleanup hook for providers that hold resources."""
        return None


# ---------------------------------------------------------------------------
# Hash-based provider (cheap, deterministic; useful for tests)
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


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based embeddings for tests / low-cost modes."""

    def __init__(
        self,
        metadata: EmbeddingMetadata,
        dimension: int | None = None,
    ) -> None:
        if dimension is not None and dimension > 0 and dimension != metadata.dimension:
            metadata = EmbeddingMetadata(
                provider=metadata.provider,
                model=metadata.model,
                dimension=dimension,
                profile=metadata.profile,
            )
        elif metadata.dimension <= 0:
            metadata = EmbeddingMetadata(
                provider=metadata.provider,
                model=metadata.model,
                dimension=64,
                profile=metadata.profile,
            )
        super().__init__(metadata)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        dim = self.metadata.dimension
        return [_hash_to_vector(t, dim) for t in texts]

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed_passages(texts)


# ---------------------------------------------------------------------------
# SentenceTransformers provider (local model)
# ---------------------------------------------------------------------------


try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by a SentenceTransformers model."""

    def __init__(
        self,
        metadata: EmbeddingMetadata,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        trust_remote_code: bool = False,
    ) -> None:
        if SentenceTransformer is None:
            raise EmbeddingConfigError(
                "sentence-transformers is not installed but "
                "SentenceTransformerEmbeddingProvider is configured"
            )

        if metadata.dimension <= 0:
            logger.warning(
                "EmbeddingMetadata.dimension is not set (>0) for profile %s; "
                "consider configuring 'dimension' in llmc.toml.",
                metadata.profile or "<default>",
            )

        super().__init__(metadata)

        self._model_name = model_name or metadata.model
        self._device = device or "cpu"
        self._batch_size = int(batch_size) if batch_size > 0 else 32
        self._normalize = bool(normalize_embeddings)

        logger.info(
            "Loading SentenceTransformers model '%s' on device '%s' (profile=%s) trust_remote_code=%s",
            self._model_name,
            self._device,
            metadata.profile or "<default>",
            trust_remote_code,
        )
        self._model = SentenceTransformer(
            self._model_name,
            device=self._device,
            trust_remote_code=trust_remote_code,
        )

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            convert_to_numpy=False,
            show_progress_bar=False,
        )

        result: list[list[float]] = []
        for vec in embeddings:
            if hasattr(vec, "tolist"):
                arr = vec.tolist()
            else:
                arr = list(vec)
            result.append([float(x) for x in arr])
        return result

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)


# ---------------------------------------------------------------------------
# Ollama provider (local/remote HTTP API)
# ---------------------------------------------------------------------------


try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by an Ollama /api/embeddings endpoint."""

    def __init__(
        self,
        metadata: EmbeddingMetadata,
        api_base: str = "http://localhost:11434",
        timeout: int = 60,
    ) -> None:
        if requests is None:
            raise EmbeddingConfigError(
                "The 'requests' library is required for OllamaEmbeddingProvider "
                "but is not installed."
            )

        super().__init__(metadata)

        self._api_base = api_base.rstrip("/")
        self._timeout = int(timeout) if timeout and timeout > 0 else 60

        logger.info(
            "Configured OllamaEmbeddingProvider(api_base=%s, model=%s, profile=%s)",
            self._api_base,
            metadata.model,
            metadata.profile or "<default>",
        )

    def _post_embedding(self, text: str) -> list[float]:
        url = f"{self._api_base}/api/embeddings"
        payload = {
            "model": self.metadata.model,
            "prompt": text,
        }
        try:
            resp = requests.post(url, json=payload, timeout=self._timeout)
        except Exception as exc:  # pragma: no cover - network error path
            raise EmbeddingError(f"Error calling Ollama embeddings endpoint: {exc}") from exc

        if resp.status_code != 200:
            raise EmbeddingError(
                f"Ollama embeddings endpoint returned {resp.status_code}: {resp.text[:200]}"
            )

        try:
            data = resp.json()
        except Exception as exc:  # pragma: no cover - bad JSON
            raise EmbeddingError(f"Invalid JSON from Ollama embeddings endpoint: {exc}") from exc

        if "embedding" in data:
            emb = data["embedding"]
        elif "embeddings" in data:
            emb = data["embeddings"][0]
        else:
            raise EmbeddingError(
                "Ollama embeddings response missing 'embedding' or 'embeddings' field"
            )

        return [float(x) for x in emb]

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(self._post_embedding(text))
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts)
