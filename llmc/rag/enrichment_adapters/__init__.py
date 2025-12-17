"""
Enrichment adapters package.

This package contains backend adapter implementations for enrichment providers.
Each adapter implements the BackendAdapter protocol from enrichment_backends.py.
"""

from llmc.rag.enrichment_adapters.anthropic import AnthropicBackend
from llmc.rag.enrichment_adapters.base import RemoteBackend
from llmc.rag.enrichment_adapters.gemini import GeminiBackend
from llmc.rag.enrichment_adapters.ollama import OllamaBackend
from llmc.rag.enrichment_adapters.openai_compat import OpenAICompatBackend

__all__ = [
    "OllamaBackend",
    "RemoteBackend",
    "GeminiBackend",
    "OpenAICompatBackend",
    "AnthropicBackend",
]
