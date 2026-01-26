"""Backend implementations for LLM inference."""

from llmc_agent.backends.base import Backend, GenerateRequest, GenerateResponse
from llmc_agent.backends.llmc import LLMCBackend, RAGResult
from llmc_agent.backends.ollama import OllamaBackend
from llmc_agent.backends.openai_compat import OpenAICompatBackend

__all__ = [
    "Backend",
    "GenerateRequest",
    "GenerateResponse",
    "OllamaBackend",
    "OpenAICompatBackend",
    "LLMCBackend",
    "RAGResult",
]
