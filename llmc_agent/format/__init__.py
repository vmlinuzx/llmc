"""Unified Tool Protocol (UTP) - Format translation layer.

This package provides format-agnostic tool calling by:
1. Parsing tool calls from any response format (native, XML, JSON)
2. Normalizing to internal ToolCall representation
3. Formatting results back to provider-expected format

Usage:
    from llmc_agent.format import FormatNegotiator, ToolCall
    
    negotiator = FormatNegotiator()
    parser = negotiator.get_call_parser()
    parsed = parser.parse(ollama_response)
    for tc in parsed.tool_calls:
        # tc is a normalized ToolCall
        result = execute_tool(tc)
"""

from llmc_agent.format.negotiator import FormatNegotiator
from llmc_agent.format.types import ParsedResponse, ToolCall, ToolFormat, ToolResult

__all__ = [
    "FormatNegotiator",
    "ParsedResponse",
    "ToolCall",
    "ToolFormat",
    "ToolResult",
]
