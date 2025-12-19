"""Parser for XML tool calls in content (Anthropic, Qwen, custom templates)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from llmc_agent.format.types import ParsedResponse, ToolCall

logger = logging.getLogger(__name__)


class XMLToolParser:
    """Parses XML tool calls from response content.
    
    Handles multiple XML formats:
    - Anthropic: <tool_use>
    - Qwen: <tools>
    - Generic: <function_call>, <tool_call>
    
    Priority 2 parser - used when native field is empty.
    """
    
    # Patterns to detect XML tool blocks (regex, format_name)
    PATTERNS = [
        (r"<tool_use>(.*?)</tool_use>", "anthropic"),
        (r"<tools>(.*?)</tools>", "qwen"),
        (r"<function_call>(.*?)</function_call>", "generic"),
        (r"<tool_call>(.*?)</tool_call>", "generic"),
    ]
    
    def can_parse(self, response: Any) -> bool:
        """Check for XML tool patterns in content."""
        content = self._extract_content(response)
        if not content:
            return False
        
        for pattern, _ in self.PATTERNS:
            if re.search(pattern, content, re.DOTALL | re.IGNORECASE):
                return True
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from XML in content."""
        content = self._extract_content(response)
        tool_calls = []
        
        for pattern, format_name in self.PATTERNS:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                block_content = match.group(1).strip()
                tc = self._parse_block(block_content, format_name)
                if tc:
                    tool_calls.append(tc)
                    logger.debug(f"Parsed {format_name} tool call: {tc.name}")
        
        # Clean content of parsed tool blocks
        clean_content = content
        for pattern, _ in self.PATTERNS:
            clean_content = re.sub(pattern, "", clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = clean_content.strip()
        
        return ParsedResponse(
            content=clean_content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            raw_response=response,
        )
    
    def _extract_content(self, response: Any) -> str:
        """Extract content string from various response formats."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            msg = response.get("message", response)
            return msg.get("content", "") or ""
        return getattr(response, "content", "") or ""
    
    def _parse_block(self, block: str, format_name: str) -> ToolCall | None:
        """Parse a single XML block to ToolCall."""
        # Try JSON first (common: <tools>{"name": "...", "arguments": {...}}</tools>)
        try:
            data = json.loads(block)
            name = data.get("name")
            args = data.get("arguments", data.get("parameters", {}))
            if name:
                return ToolCall(name=name, arguments=args, raw=block)
        except json.JSONDecodeError:
            pass
        
        # Try line-based parsing (name on first line, JSON on rest)
        lines = block.strip().split("\n")
        if len(lines) >= 1:
            # Check if first line is just the tool name
            first_line = lines[0].strip()
            if first_line and not first_line.startswith("{"):
                try:
                    rest = "\n".join(lines[1:]).strip()
                    args = json.loads(rest) if rest else {}
                    return ToolCall(name=first_line, arguments=args, raw=block)
                except json.JSONDecodeError:
                    pass
        
        logger.warning(f"Could not parse {format_name} block: {block[:100]}...")
        return None
