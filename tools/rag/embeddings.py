from __future__ import annotations

import logging
from typing import List, Tuple, Optional
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
from .embedding_providers import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    HashEmbeddingProvider,
)

logger = logging.getLogger(__name__)


# This module will now act as a factory/manager for EmbeddingProviders
# The actual backend implementations (Ollama, SentenceTransformer, Hash)
# are moved into tools/rag/embedding_providers.py


class EmbeddingManager:
    """
    Manages the selection and instantiation of embedding providers based on configuration.
    This class now serves as the central point for accessing embedding functionalities.
    """
    _instance: Optional[EmbeddingProvider] = None

    def __init__(self, provider: EmbeddingProvider):
        self._provider = provider

    @classmethod
    def get_instance(cls) -> EmbeddingManager:
        """
        Returns a singleton instance of EmbeddingManager, ensuring only one provider
        is loaded based on configuration.
        """
        if cls._instance is None:
            cls._instance = cls._build_provider_from_config()
        return cls(cls._instance)

    @classmethod
    def _build_provider_from_config(cls) -> EmbeddingProvider:
        """
        Internal method to build the embedding provider based on llmc.toml config.
        """
        model_name = embedding_model_name()
        dim = embedding_model_dim()
        normalize = embedding_normalize()
        passage_prefix = embedding_passage_prefix()
        query_prefix = embedding_query_prefix()
        preset = embedding_model_preset()

        if preset == "ollama": # Assuming preset 'ollama' means Ollama API based provider
            return OllamaEmbeddingProvider(
                model_name=model_name,
                dim=dim, # Ollama provider might fetch this dynamically or use config
                normalize=normalize,
                passage_prefix=passage_prefix,
                query_prefix=query_prefix,
            )
        elif preset == "sentence-transformer":
            # This provider will handle its own device selection internally
            return SentenceTransformerEmbeddingProvider(
                model_name=model_name,
                dim=dim,
                normalize=normalize,
                passage_prefix=passage_prefix,
                query_prefix=query_prefix,
                device_preference=embedding_device_preference(),
                gpu_max_retries=embedding_gpu_max_retries(),
                gpu_min_free_mb=embedding_gpu_min_free_mb(),
                gpu_retry_seconds=embedding_gpu_retry_seconds(),
                wait_for_gpu=embedding_wait_for_gpu(),
            )
        elif preset == "hash":
            return HashEmbeddingProvider(
                model_name=model_name,
                dim=dim,
                normalize=normalize,
                passage_prefix=passage_prefix,
                query_prefix=query_prefix,
            )
        else:
            raise ValueError(f"Unsupported embedding model preset: {preset}")

    @property
    def model_name(self) -> str:
        return self._provider.get_model_name()

    @property
    def dim(self) -> int:
        return self._provider.get_dimension()

    def embed_passages(self, texts: Sequence[str]) -> List[List[float]]:
        return self._provider.embed_passages(texts)

    def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        return self._provider.embed_queries(texts)

    def format_passages(self, raw_texts: Iterable[str]) -> List[str]:
        return self._provider.format_passages(raw_texts)

    def format_queries(self, raw_texts: Iterable[str]) -> List[str]:
        return self._provider.format_queries(raw_texts)


# --- Old `generate_embeddings` function rewritten to use the manager ---
def generate_embeddings(
    texts: List[str], is_query: bool = False
) -> List[List[float]]:
    """
    Generates embeddings for a list of texts using the configured embedding provider.
    """
    manager = EmbeddingManager.get_instance()
    if is_query:
        return manager.embed_queries(texts)
    else:
        return manager.embed_passages(texts)

# This is still here because other parts of the system might call it.
# Ideally, we should transition all callers to use EmbeddingManager.get_instance().embed_passages/queries
def embedding_model_spec() -> EmbeddingSpec:
    """Returns the EmbeddingSpec for the currently active embedding model."""
    manager = EmbeddingManager.get_instance()
    return EmbeddingSpec(
        model_name=manager.model_name,
        dim=manager.dim,
        passage_prefix=embedding_passage_prefix(), # These are still global config
        query_prefix=embedding_query_prefix(),     # but could be moved to provider spec
        normalize=embedding_normalize(),
    )


# --- Re-add the EmbeddingSpec dataclass, as it's still useful for metadata ---
@dataclass(frozen=True)
class EmbeddingSpec:
    model_name: str
    dim: int
    passage_prefix: str
    query_prefix: str
    normalize: bool

