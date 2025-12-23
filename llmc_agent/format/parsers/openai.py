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
    
    Supports both:
    - Ollama format: response.message.tool_calls
    - OpenAI format: response.choices[0].message.tool_calls
    """
    
    def _extract_message(self, response: Any) -> dict | None:
        """Extract the message object from various response formats."""
        if not isinstance(response, dict):
            return None
        
        # Try OpenAI format: choices[0].message
        choices = response.get("choices")
        if choices and isinstance(choices, list) and len(choices) > 0:
            choice = choices[0]
            if isinstance(choice, dict):
                msg = choice.get("message")
                if isinstance(msg, dict):
                    return msg
        
        # Try Ollama format: response.message
        msg = response.get("message")
        if isinstance(msg, dict):
            return msg
        
        # Try direct format (already the message)
        if "tool_calls" in response or "content" in response:
            return response
        
        return None
    
    def can_parse(self, response: Any) -> bool:
        """Check for tool_calls in response.
        
        Looks for tool_calls in either:
        - response.choices[0].message.tool_calls (OpenAI format)
        - response.message.tool_calls (Ollama format)
        - response.tool_calls (direct)
        """
        msg = self._extract_message(response)
        if msg is None:
            return False
        tool_calls = msg.get("tool_calls")
        return bool(tool_calls)
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from native field.
        
        Handles both string and dict argument formats.
        """
        msg = self._extract_message(response)
        
        if msg is None:
            tool_calls_raw = []
            content = ""
        else:
            tool_calls_raw = msg.get("tool_calls", []) or []
            content = msg.get("content", "") or ""
        
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

