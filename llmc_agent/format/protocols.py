"""Protocol definitions for format adapters and parsers.

These protocols define the contracts that all parsers and adapters
must implement for the UTP layer to work correctly.
"""

from typing import Any, Protocol, runtime_checkable

from llmc_agent.format.types import ParsedResponse, ToolCall, ToolResult


@runtime_checkable
class ToolCallParser(Protocol):
    """Extracts tool calls from model responses.
    
    Implementations must be able to detect whether they can handle
    a given response format and extract tool calls if so.
    """
    
    def can_parse(self, response: Any) -> bool:
        """Check if this parser can handle the response.
        
        Args:
            response: Raw response from LLM provider
            
        Returns:
            True if this parser can extract tool calls from the response
        """
        ...
    
    def parse(self, response: Any) -> ParsedResponse:
        """Parse response and extract tool calls.
        
        Args:
            response: Raw response from LLM provider
            
        Returns:
            ParsedResponse with content and any tool calls found
        """
        ...


@runtime_checkable
class ToolDefinitionAdapter(Protocol):
    """Converts internal tool definitions to provider format.
    
    Used when sending tool definitions to the LLM provider.
    """
    
    def format_tools(self, tools: list) -> Any:
        """Convert tools to provider-specific format.
        
        Args:
            tools: List of internal Tool objects
            
        Returns:
            Provider-specific tool definition format
        """
        ...


@runtime_checkable
class ToolResultAdapter(Protocol):
    """Converts tool results to provider message format.
    
    Used when injecting tool results back into the conversation.
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to provider-specific message.
        
        Args:
            call: The original tool call
            result: The result of executing the tool
            
        Returns:
            Message dict suitable for the provider's conversation format
        """
        ...
