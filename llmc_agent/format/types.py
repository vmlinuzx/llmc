"""Internal representations for Unified Tool Protocol (UTP).

This module defines the core data types that serve as the lingua franca
for tool calling across different LLM providers and formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolFormat(Enum):
    """Supported tool calling formats."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AUTO = "auto"


@dataclass
class ToolCall:
    """Normalized tool call - the lingua franca.
    
    This is the internal representation that all parsers produce,
    regardless of the original format (OpenAI native, XML, etc.).
    """
    name: str
    arguments: dict[str, Any]
    id: str | None = None
    raw: Any = None  # Original format for debugging


@dataclass
class ToolResult:
    """Normalized tool result.
    
    Wraps the result of executing a tool, including error handling.
    """
    call_id: str | None
    tool_name: str
    result: Any
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class ParsedResponse:
    """Result of parsing a model response.
    
    Contains both the text content and any extracted tool calls.
    """
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    raw_response: Any = None
