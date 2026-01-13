"""Anthropic format adapters (stub for future implementation)."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from llmc_agent.format.types import ToolCall, ToolResult


class AnthropicResultAdapter:
    """Formats tool results for Anthropic conversation.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")


class AnthropicDefinitionAdapter:
    """Formats tool definitions for Anthropic API."""
    
    def format_tools(self, tools: list) -> str:
        """Convert internal Tool objects to Anthropic XML format.

        Args:
            tools: List of Tool objects or dicts defining tools.

        Returns:
            String containing the XML formatted tool definitions.
        """
        parts = ["<tools>"]

        for tool in tools:
            # Handle both Tool dataclass and dict
            # Use getattr with default empty string for robustness
            if isinstance(tool, dict):
                name = tool.get("name", "")
                description = tool.get("description", "")
                parameters = tool.get("parameters", {})
            else:
                name = getattr(tool, "name", "")
                description = getattr(tool, "description", "")
                parameters = getattr(tool, "parameters", {})

            parts.append("<tool_description>")
            parts.append(f"<tool_name>{escape(str(name))}</tool_name>")
            parts.append(f"<description>{escape(str(description))}</description>")
            parts.append("<parameters>")

            properties = parameters.get("properties", {})
            required_params = parameters.get("required", [])

            for param_name, param_info in properties.items():
                parts.append("<parameter>")
                parts.append(f"<name>{escape(str(param_name))}</name>")

                # Handle type
                param_type = param_info.get("type", "string")
                parts.append(f"<type>{escape(str(param_type))}</type>")

                # Handle description and enums
                param_desc = param_info.get("description", "")
                enum_values = param_info.get("enum")

                if enum_values:
                    enum_str = f"Allowed values: {', '.join(map(str, enum_values))}"
                    if param_desc:
                        param_desc = f"{param_desc}. {enum_str}"
                    else:
                        param_desc = enum_str

                if param_desc:
                    parts.append(f"<description>{escape(str(param_desc))}</description>")

                # Handle required
                if param_name in required_params:
                    parts.append("<required>true</required>")

                parts.append("</parameter>")

            parts.append("</parameters>")
            parts.append("</tool_description>")

        parts.append("</tools>")

        return "\n".join(parts)
