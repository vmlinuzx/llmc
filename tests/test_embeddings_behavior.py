import math

from tools.rag.embeddings import (
    EmbeddingSpec,
    HashEmbeddingBackend,
    ManagerEmbeddingBackend,
    build_embedding_backend,
)


def test_hash_backend_normalization() -> None:
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=16,
        passage_prefix="",
        query_prefix="",
        normalize=True,
    )
    backend = HashEmbeddingBackend(spec)

    vector = backend.embed_passages(["hello world"])[0]
    magnitude = math.sqrt(sum(x * x for x in vector))
    assert math.isclose(magnitude, 1.0, rel_tol=1e-6)


def test_factory_selects_hash_vs_manager() -> None:
    hash_backend = build_embedding_backend("hash-emb-v1", dim=16)
    assert isinstance(hash_backend, HashEmbeddingBackend)
    assert hash_backend.dim == 16

    manager_backend = build_embedding_backend("some-real-model", dim=384)
    assert isinstance(manager_backend, ManagerEmbeddingBackend)
    assert manager_backend.dim == 384


def test_hash_backend_empty_input() -> None:
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=8,
        passage_prefix="",
        query_prefix="",
        normalize=False,
    )
    backend = HashEmbeddingBackend(spec)

    assert backend.embed_passages([]) == []

    vec = backend.embed_passages([""])[0]
    assert len(vec) == 8
    assert any(x != 0 for x in vec)


def test_large_dimension() -> None:
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=1024,
        passage_prefix="",
        query_prefix="",
        normalize=False,
    )
    backend = HashEmbeddingBackend(spec)
    vec = backend.embed_passages(["stress test"])[0]
    assert len(vec) == 1024
