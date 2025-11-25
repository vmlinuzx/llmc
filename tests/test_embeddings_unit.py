import math

from tools.rag.embeddings import EmbeddingSpec, HashEmbeddingBackend


def test_hash_backend_is_deterministic():
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=16,
        passage_prefix="ctx: ",
        query_prefix="q: ",
        normalize=False,
    )
    backend = HashEmbeddingBackend(spec)

    first = backend.embed_passages(["hello world"])[0]
    second = backend.embed_passages(["hello world"])[0]

    assert first == second
    assert len(first) == spec.dim
    assert all(-1.0 <= value <= 1.0 for value in first)


def test_formatters_apply_prefixes():
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=4,
        passage_prefix="passage: ",
        query_prefix="query: ",
        normalize=False,
    )
    backend = HashEmbeddingBackend(spec)

    passages = backend.format_passages([" Code snippet "])
    queries = backend.format_queries(["What is up?"])

    assert passages == ["passage: Code snippet"]
    assert queries == ["query: What is up?"]


def test_hash_backend_respects_dimension():
    spec = EmbeddingSpec(
        model_name="hash-emb-v1",
        dim=8,
        passage_prefix="",
        query_prefix="",
        normalize=False,
    )
    backend = HashEmbeddingBackend(spec)

    vectors = backend.embed_passages(["one", "two"])
    assert len(vectors) == 2
    assert all(len(vec) == spec.dim for vec in vectors)

    # ensure output spans multiple magnitudes rather than collapsing to zeros
    magnitudes = [math.sqrt(sum(value * value for value in vec)) for vec in vectors]
    assert all(mag > 0 for mag in magnitudes)
