"""Parser for OpenAI/Ollama native tool_calls field."""

from __future__ import annotations

import json
from typing import Any

from llmc_agent.format.types import ParsedResponse, ToolCall


class OpenAINativeParser:
    """Parses OpenAI/Ollama native tool_calls field.
    
    Priority 1 parser - checks the structured API field first.
    This handles responses where tool calls are returned in the
    standard OpenAI format with a `tool_calls` array.
    """
    
    def can_parse(self, response: Any) -> bool:
        """Check for tool_calls in response.
        
        Looks for tool_calls in either:
        - response.message.tool_calls (Ollama format)
        - response.tool_calls (direct)
        """
        if isinstance(response, dict):
            msg = response.get("message", response)
            tool_calls = msg.get("tool_calls")
            return bool(tool_calls)
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from native field.
        
        Handles both string and dict argument formats.
        """
        if isinstance(response, dict):
            msg = response.get("message", response)
            tool_calls_raw = msg.get("tool_calls", []) or []
            content = msg.get("content", "") or ""
        else:
            tool_calls_raw = []
            content = ""
        
        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", tc)
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            
            tool_calls.append(ToolCall(
                name=func.get("name", ""),
                arguments=args,
                id=tc.get("id"),
                raw=tc,
            ))
        
        return ParsedResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            raw_response=response,
        )
