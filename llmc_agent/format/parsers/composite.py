"""Composite parser that tries multiple parsers in priority order."""

from __future__ import annotations

import logging
from typing import Any

from llmc_agent.format.types import ParsedResponse

logger = logging.getLogger(__name__)


class CompositeParser:
    """Tries multiple parsers in priority order.
    
    Default parser that handles any response format by trying:
    1. OpenAI native (tool_calls field)
    2. XML in content
    
    Returns the first successful parse that contains tool calls,
    or a ParsedResponse with empty tool_calls if none found.
    """
    
    def __init__(self, parsers: list | None = None):
        if parsers is None:
            from llmc_agent.format.parsers.openai import OpenAINativeParser
            from llmc_agent.format.parsers.xml import XMLToolParser
            
            self.parsers = [
                OpenAINativeParser(),
                XMLToolParser(),
            ]
        else:
            self.parsers = parsers
    
    def can_parse(self, response: Any) -> bool:
        """Always returns True - we're the catch-all."""
        return True
    
    def parse(self, response: Any) -> ParsedResponse:
        """Try parsers in order, return first successful result."""
        content = self._extract_content(response)
        
        for parser in self.parsers:
            if parser.can_parse(response):
                result = parser.parse(response)
                if result.tool_calls:
                    logger.info(f"Parsed {len(result.tool_calls)} tool call(s) via {parser.__class__.__name__}")
                    return result
        
        # No tool calls found by any parser
        return ParsedResponse(
            content=content,
            tool_calls=[],
            finish_reason="stop",
            raw_response=response,
        )
    
    def _extract_content(self, response: Any) -> str:
        """Extract content from response."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            msg = response.get("message", response)
            if msg is None:
                return ""
            if isinstance(msg, dict):
                return msg.get("content", "") or ""
            return ""
        return getattr(response, "content", "") or ""
