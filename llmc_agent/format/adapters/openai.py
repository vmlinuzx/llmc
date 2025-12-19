"""OpenAI/Ollama format adapters."""

from __future__ import annotations

import json
from typing import Any

from llmc_agent.format.types import ToolCall, ToolResult


class OpenAIResultAdapter:
    """Formats tool results for OpenAI/Ollama conversation.
    
    Converts internal ToolResult to the message format expected
    by OpenAI-compatible APIs.
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to OpenAI-style tool message.
        
        Args:
            call: The original tool call
            result: The result of executing the tool
            
        Returns:
            Message dict with role='tool' and the result content
        """
        content = result.result if result.success else {"error": result.error}
        
        return {
            "role": "tool",
            "tool_call_id": call.id or "",
            "content": json.dumps(content) if not isinstance(content, str) else content,
        }


class OpenAIDefinitionAdapter:
    """Formats tool definitions for OpenAI/Ollama API.
    
    Converts internal Tool objects to the function format expected
    by OpenAI-compatible APIs.
    """
    
    def format_tools(self, tools: list) -> list[dict[str, Any]]:
        """Convert internal Tool objects to OpenAI format.
        
        Args:
            tools: List of Tool objects (from llmc_agent.tools)
            
        Returns:
            List of OpenAI-format tool definitions
        """
        result = []
        for tool in tools:
            # Handle both Tool dataclass and dict
            if hasattr(tool, "to_ollama_format"):
                result.append(tool.to_ollama_format())
            elif hasattr(tool, "name"):
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": getattr(tool, "description", ""),
                        "parameters": getattr(tool, "parameters", {}),
                    }
                })
            elif isinstance(tool, dict):
                # Already in dict format
                if "type" in tool and "function" in tool:
                    result.append(tool)
                else:
                    result.append({
                        "type": "function",
                        "function": {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        }
                    })
        return result
