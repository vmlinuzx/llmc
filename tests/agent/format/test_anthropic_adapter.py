"""Tests for Anthropic format adapters."""

import pytest
from llmc_agent.tools import Tool, ToolTier
from llmc_agent.format.adapters.anthropic import AnthropicDefinitionAdapter

class TestAnthropicDefinitionAdapter:

    def test_format_tools_simple(self):
        # Create a simple tool
        tool = Tool(
            name="get_weather",
            description="Get the weather for a location",
            tier=ToolTier.CRAWL,
            function=lambda x: x,
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and state"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of temperature",
                        "enum": ["celsius", "fahrenheit"]
                    }
                },
                "required": ["location"]
            }
        )

        adapter = AnthropicDefinitionAdapter()
        formatted = adapter.format_tools([tool])

        assert isinstance(formatted, str)
        assert "<tools>" in formatted
        assert "</tools>" in formatted
        assert "<tool_description>" in formatted
        assert "<tool_name>get_weather</tool_name>" in formatted
        assert "<description>Get the weather for a location</description>" in formatted

        # Check parameters
        assert "<parameters>" in formatted
        assert "<parameter>" in formatted
        assert "<name>location</name>" in formatted
        assert "<type>string</type>" in formatted
        assert "<description>City and state</description>" in formatted
        assert "<required>true</required>" in formatted # logic for required

        # Check second parameter and enum
        assert "<name>unit</name>" in formatted
        assert "<type>string</type>" in formatted
        assert "Allowed values: celsius, fahrenheit" in formatted

    def test_format_tools_multiple(self):
        tool1 = Tool(
            name="tool1",
            description="Description 1",
            tier=ToolTier.CRAWL,
            function=lambda: None,
            parameters={"type": "object", "properties": {"a": {"type": "string"}}}
        )
        tool2 = Tool(
            name="tool2",
            description="Description 2",
            tier=ToolTier.CRAWL,
            function=lambda: None,
            parameters={"type": "object", "properties": {"b": {"type": "string"}}}
        )

        adapter = AnthropicDefinitionAdapter()
        formatted = adapter.format_tools([tool1, tool2])

        assert "<tool_name>tool1</tool_name>" in formatted
        assert "<tool_name>tool2</tool_name>" in formatted

    def test_format_tools_dict(self):
        """Test formatting tool provided as dictionary."""
        tool_dict = {
            "name": "dict_tool",
            "description": "A tool from a dict",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg": {"type": "integer"}
                }
            }
        }

        adapter = AnthropicDefinitionAdapter()
        formatted = adapter.format_tools([tool_dict])

        assert "<tool_name>dict_tool</tool_name>" in formatted
        assert "<description>A tool from a dict</description>" in formatted
        assert "<name>arg</name>" in formatted
        assert "<type>integer</type>" in formatted

    def test_xml_escaping(self):
        """Test that special XML characters are escaped."""
        tool = Tool(
            name="compare<>&",
            description="Compares A & B <C>",
            tier=ToolTier.CRAWL,
            function=lambda: None,
            parameters={
                "type": "object",
                "properties": {
                    "input<1>": {
                        "type": "string",
                        "description": "Input <value>"
                    }
                }
            }
        )

        adapter = AnthropicDefinitionAdapter()
        formatted = adapter.format_tools([tool])

        assert "compare&lt;&gt;&amp;" in formatted
        assert "Compares A &amp; B &lt;C&gt;" in formatted
        assert "input&lt;1&gt;" in formatted
        assert "Input &lt;value&gt;" in formatted
