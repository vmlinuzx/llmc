"""Backend implementations for LLM inference."""

from llmc_agent.backends.base import Backend, GenerateRequest, GenerateResponse
from llmc_agent.backends.llmc import LLMCBackend, RAGResult
from llmc_agent.backends.ollama import OllamaBackend

__all__ = [
    "Backend",
    "GenerateRequest",
    "GenerateResponse",
    "OllamaBackend",
    "LLMCBackend",
    "RAGResult",
]
