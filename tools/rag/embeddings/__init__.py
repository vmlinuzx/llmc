"""
Embeddings package.
"""

from .core import (
    HASH_MODELS,
    EmbeddingSpec,
    HashEmbeddingBackend,
    ManagerEmbeddingBackend,
    build_embedding_backend,
    embedding_model_spec,
    generate_embeddings,
    embed_passages,
    embed_queries,
)
from .hf_longcontext_adapter import LongContextAdapter
from .medical import MedicalEmbeddingManager

__all__ = [
    "HASH_MODELS",
    "EmbeddingSpec",
    "HashEmbeddingBackend",
    "ManagerEmbeddingBackend",
    "build_embedding_backend",
    "embedding_model_spec",
    "generate_embeddings",
    "embed_passages",
    "embed_queries",
    "LongContextAdapter",
    "MedicalEmbeddingManager",
]