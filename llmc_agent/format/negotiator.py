"""Format negotiation and factory for adapters/parsers."""

from __future__ import annotations

from typing import Any

from llmc_agent.format.types import ToolFormat
from llmc_agent.format.parsers import CompositeParser, OpenAINativeParser, XMLToolParser
from llmc_agent.format.adapters import OpenAIDefinitionAdapter, OpenAIResultAdapter


class FormatNegotiator:
    """Central factory for format adapters and parsers.
    
    Determines appropriate format based on:
    1. Explicit configuration (profile.tools.*)
    2. Provider defaults
    
    Usage:
        negotiator = FormatNegotiator()
        parser = negotiator.get_call_parser()
        parsed = parser.parse(response)
    """
    
    PROVIDER_DEFAULTS = {
        "openai": ToolFormat.OPENAI,
        "anthropic": ToolFormat.ANTHROPIC,
        "ollama": ToolFormat.OLLAMA,
        "gemini": ToolFormat.OPENAI,
    }
    
    def __init__(self, config: dict | None = None):
        """Initialize negotiator with optional config.
        
        Args:
            config: Optional dict with keys like 'call_parser', 
                   'definition_format', 'result_format'
        """
        self.config = config or {}
        # Cache adapters/parsers per format
        self._parser_cache: dict[ToolFormat, Any] = {}
        self._def_adapter_cache: dict[ToolFormat, Any] = {}
        self._result_adapter_cache: dict[ToolFormat, Any] = {}
    
    def detect_format(self, provider: str, model: str = "") -> ToolFormat:
        """Determine tool format for provider/model combination.
        
        Args:
            provider: Provider name (ollama, openai, anthropic, etc.)
            model: Optional model name for format hints
            
        Returns:
            Detected ToolFormat
        """
        # Check explicit config first
        if self.config.get("call_parser"):
            fmt = self.config["call_parser"]
            if fmt != "auto":
                try:
                    return ToolFormat(fmt)
                except ValueError:
                    pass  # Fall through to defaults
        
        # Provider defaults
        return self.PROVIDER_DEFAULTS.get(provider.lower(), ToolFormat.AUTO)
    
    def get_call_parser(self, format: ToolFormat | None = None):
        """Get parser for extracting tool calls.
        
        Args:
            format: Optional explicit format. If None, uses AUTO.
            
        Returns:
            Parser instance implementing ToolCallParser protocol
        """
        format = format or ToolFormat.AUTO
        
        if format not in self._parser_cache:
            if format == ToolFormat.AUTO:
                self._parser_cache[format] = CompositeParser()
            elif format in (ToolFormat.OPENAI, ToolFormat.OLLAMA):
                # OpenAI/Ollama: try native first, then XML
                self._parser_cache[format] = CompositeParser([
                    OpenAINativeParser(),
                    XMLToolParser(),
                ])
            elif format == ToolFormat.ANTHROPIC:
                # Anthropic: try XML first (their native format), then native
                self._parser_cache[format] = CompositeParser([
                    XMLToolParser(),
                    OpenAINativeParser(),
                ])
            else:
                self._parser_cache[format] = CompositeParser()
        
        return self._parser_cache[format]
    
    def get_definition_adapter(self, format: ToolFormat | None = None):
        """Get adapter for formatting tool definitions.
        
        Args:
            format: Optional explicit format. If None, uses OPENAI.
            
        Returns:
            Adapter instance implementing ToolDefinitionAdapter protocol
        """
        format = format or ToolFormat.OPENAI
        
        if format not in self._def_adapter_cache:
            # All formats use OpenAI adapter for now (Ollama is OpenAI-compatible)
            self._def_adapter_cache[format] = OpenAIDefinitionAdapter()
        
        return self._def_adapter_cache[format]
    
    def get_result_adapter(self, format: ToolFormat | None = None):
        """Get adapter for formatting tool results.
        
        Args:
            format: Optional explicit format. If None, uses OPENAI.
            
        Returns:
            Adapter instance implementing ToolResultAdapter protocol
        """
        format = format or ToolFormat.OPENAI
        
        if format not in self._result_adapter_cache:
            self._result_adapter_cache[format] = OpenAIResultAdapter()
        
        return self._result_adapter_cache[format]
