"""Anthropic format adapters."""

from __future__ import annotations

import json
from typing import Any

from llmc_agent.format.types import ToolCall, ToolResult


class AnthropicResultAdapter:
    """Formats tool results for Anthropic conversation.
    
    Converts internal ToolResult to the message format expected
    by Anthropic's Messages API (tool_result block in user message).
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to Anthropic tool result block.

        Args:
            call: The original tool call
            result: The result of executing the tool

        Returns:
            Dict representing a user message containing the tool result block
        """
        # Format content
        if result.success:
            content = result.result
            if not isinstance(content, str):
                content = json.dumps(content)
            is_error = False
        else:
            content = result.error or "Unknown error"
            is_error = True

        # Construct tool_result block
        block = {
            "type": "tool_result",
            "tool_use_id": call.id or "",
            "content": content,
            "is_error": is_error,
        }

        # Wrap in user message
        return {
            "role": "user",
            "content": [block],
        }


class AnthropicDefinitionAdapter:
    """Formats tool definitions for Anthropic API.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_tools(self, tools: list) -> str:
        """Convert internal Tool objects to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")
