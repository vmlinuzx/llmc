"""RAG Repo package init.
Provides a legacy `cli` attribute for older tests/tools that import `tools.rag_repo.cli`.
"""

try:
    from .cli import cli  # type: ignore
except Exception:  # pragma: no cover
    # Provide a clear failure path if cli module is not present
    def cli(*_a, **_k):
        raise RuntimeError(
            "tools.rag_repo.cli not found; ensure tools/rag_repo/cli.py exports a callable `cli`."
        )


"""LLMC RAG Repo Registration Tool package.

Provides the `llmc-rag-repo` CLI to onboard repos into the LLMC RAG system.
"""
