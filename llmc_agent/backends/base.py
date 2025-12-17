"""Abstract backend interface for LLM inference."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerateRequest:
    """Request to generate a response."""

    messages: list[dict]  # OpenAI-style messages
    system: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024


@dataclass
class GenerateResponse:
    """Response from generation."""

    content: str
    tokens_prompt: int
    tokens_completion: int
    model: str
    finish_reason: str  # "stop", "length", "error", "tool_calls"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class Backend(ABC):
    """Abstract backend for LLM inference."""

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a response (non-streaming)."""
        pass

    @abstractmethod
    async def generate_stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        """Generate a response with streaming."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if backend is available."""
        pass
