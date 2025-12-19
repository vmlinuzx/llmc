"""Anthropic format adapters (stub for future implementation)."""

from __future__ import annotations

from typing import Any

from llmc_agent.format.types import ToolCall, ToolResult


class AnthropicResultAdapter:
    """Formats tool results for Anthropic conversation.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")


class AnthropicDefinitionAdapter:
    """Formats tool definitions for Anthropic API.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_tools(self, tools: list) -> str:
        """Convert internal Tool objects to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")
