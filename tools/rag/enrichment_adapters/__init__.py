"""
Enrichment adapters package.

This package contains backend adapter implementations for enrichment providers.
Each adapter implements the BackendAdapter protocol from enrichment_backends.py.
"""

from tools.rag.enrichment_adapters.ollama import OllamaBackend

__all__ = ["OllamaBackend"]
