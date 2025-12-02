"""
Enrichment adapters package.

This package contains backend adapter implementations for enrichment providers.
Each adapter implements the BackendAdapter protocol from enrichment_backends.py.
"""

from tools.rag.enrichment_adapters.ollama import OllamaBackend
from tools.rag.enrichment_adapters.base import RemoteBackend
from tools.rag.enrichment_adapters.gemini import GeminiBackend
from tools.rag.enrichment_adapters.openai_compat import OpenAICompatBackend
from tools.rag.enrichment_adapters.anthropic import AnthropicBackend

__all__ = [
    "OllamaBackend",
    "RemoteBackend",
    "GeminiBackend",
    "OpenAICompatBackend",
    "AnthropicBackend",
]
