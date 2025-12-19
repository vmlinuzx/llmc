"""
Embeddings package.

Heavy backends (LongContextAdapter, MedicalEmbeddingManager) are lazy-loaded
to avoid 5+ second torch/transformers import time on every CLI invocation.
"""

from .core import (
    HASH_MODELS,
    EmbeddingSpec,
    HashEmbeddingBackend,
    ManagerEmbeddingBackend,
    build_embedding_backend,
    embed_passages,
    embed_queries,
    embedding_model_spec,
    generate_embeddings,
)

# Lazy imports for heavy backends (torch/transformers)
# These are only imported when actually accessed


def __getattr__(name: str):
    """Lazy import heavy backends to avoid 5+ second startup penalty."""
    if name == "LongContextAdapter":
        from .hf_longcontext_adapter import LongContextAdapter
        return LongContextAdapter
    if name == "MedicalEmbeddingManager":
        from .medical import MedicalEmbeddingManager
        return MedicalEmbeddingManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
