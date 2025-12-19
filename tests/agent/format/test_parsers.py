"""Unit tests for UTP parsers."""

import pytest
from llmc_agent.format.parsers import CompositeParser, OpenAINativeParser, XMLToolParser


class TestOpenAINativeParser:
    """Tests for OpenAI native tool_calls field parser."""

    def test_can_parse_with_tool_calls(self):
        """Parser should detect when tool_calls are present."""
        response = {"message": {"tool_calls": [{"function": {"name": "test"}}]}}
        parser = OpenAINativeParser()
        assert parser.can_parse(response) is True

    def test_can_parse_without_tool_calls(self):
        """Parser should return False when no tool_calls."""
        response = {"message": {"content": "Hello"}}
        parser = OpenAINativeParser()
        assert parser.can_parse(response) is False

    def test_can_parse_empty_tool_calls(self):
        """Parser should return False for empty tool_calls list."""
        response = {"message": {"tool_calls": []}}
        parser = OpenAINativeParser()
        assert parser.can_parse(response) is False

    def test_parse_extracts_single_tool_call(self):
        """Parser should extract a single tool call correctly."""
        response = {
            "message": {
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "search_code",
                        "arguments": '{"query": "test"}'
                    }
                }]
            }
        }
        parser = OpenAINativeParser()
        parsed = parser.parse(response)
        
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].arguments == {"query": "test"}
        assert parsed.tool_calls[0].id == "call_123"

    def test_parse_extracts_multiple_tool_calls(self):
        """Parser should handle multiple tool calls."""
        response = {
            "message": {
                "tool_calls": [
                    {"function": {"name": "tool1", "arguments": "{}"}},
                    {"function": {"name": "tool2", "arguments": '{"x": 1}'}},
                ]
            }
        }
        parser = OpenAINativeParser()
        parsed = parser.parse(response)
        
        assert len(parsed.tool_calls) == 2
        assert parsed.tool_calls[0].name == "tool1"
        assert parsed.tool_calls[1].name == "tool2"

    def test_parse_handles_dict_arguments(self):
        """Parser should handle arguments as dict (not string)."""
        response = {
            "message": {
                "tool_calls": [{
                    "function": {
                        "name": "test",
                        "arguments": {"key": "value"}  # Already a dict
                    }
                }]
            }
        }
        parser = OpenAINativeParser()
        parsed = parser.parse(response)
        
        assert parsed.tool_calls[0].arguments == {"key": "value"}

    def test_parse_handles_malformed_json_arguments(self):
        """Parser should handle malformed JSON arguments gracefully."""
        response = {
            "message": {
                "tool_calls": [{
                    "function": {
                        "name": "test",
                        "arguments": "not valid json"
                    }
                }]
            }
        }
        parser = OpenAINativeParser()
        parsed = parser.parse(response)
        
        # Should not crash, should return empty dict for arguments
        assert parsed.tool_calls[0].name == "test"
        assert parsed.tool_calls[0].arguments == {}


class TestXMLToolParser:
    """Tests for XML tool call parser (Anthropic, Qwen, etc.)."""

    def test_can_parse_qwen_format(self):
        """Parser should detect Qwen <tools> tags."""
        response = {"message": {"content": '<tools>{"name": "test"}</tools>'}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is True

    def test_can_parse_anthropic_format(self):
        """Parser should detect Anthropic <tool_use> tags."""
        response = {"message": {"content": '<tool_use>{"name": "test"}</tool_use>'}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is True

    def test_can_parse_function_call_format(self):
        """Parser should detect <function_call> tags."""
        response = {"message": {"content": '<function_call>{"name": "test"}</function_call>'}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is True

    def test_can_parse_returns_false_for_plain_text(self):
        """Parser should return False for content without XML tags."""
        response = {"message": {"content": "Just some text"}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is False

    def test_parse_qwen_format(self):
        """Parser should extract tool calls from Qwen XML format."""
        response = {
            "message": {
                "content": 'I will search.\n\n<tools>\n{"name": "search_code", "arguments": {"query": "auth"}}\n</tools>'
            }
        }
        parser = XMLToolParser()
        parsed = parser.parse(response)
        
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].arguments == {"query": "auth"}
        assert "I will search." in parsed.content

    def test_parse_anthropic_format(self):
        """Parser should extract tool calls from Anthropic XML format."""
        response = {
            "message": {
                "content": '<tool_use>{"name": "read_file", "arguments": {"path": "foo.py"}}</tool_use>'
            }
        }
        parser = XMLToolParser()
        parsed = parser.parse(response)
        
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "read_file"

    def test_parse_removes_xml_from_content(self):
        """Parser should remove XML tool blocks from content."""
        response = {
            "message": {
                "content": 'Before <tools>{"name": "x", "arguments": {}}</tools> After'
            }
        }
        parser = XMLToolParser()
        parsed = parser.parse(response)
        
        assert "<tools>" not in parsed.content
        assert "</tools>" not in parsed.content
        assert "Before" in parsed.content
        assert "After" in parsed.content

    def test_parse_handles_malformed_json(self):
        """Parser should handle malformed JSON in XML gracefully.
        
        Note: The parser has a fallback that treats single-line content
        as a potential tool name, so 'not valid json' becomes a tool call
        with empty arguments. This is by design for lenient parsing.
        Multi-line malformed content is handled differently.
        """
        # Multi-line malformed JSON should result in empty tool_calls
        response = {"message": {"content": "<tools>{\nbroken\njson\n}</tools>"}}
        parser = XMLToolParser()
        parsed = parser.parse(response)  # Should not raise
        
        # Multi-line can't be parsed as JSON or as name+args, so empty
        assert parsed.tool_calls == []

    def test_parse_case_insensitive(self):
        """Parser should handle case variations in XML tags."""
        response = {"message": {"content": '<TOOLS>{"name": "test", "arguments": {}}</TOOLS>'}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is True


class TestCompositeParser:
    """Tests for composite parser that tries multiple parsers."""

    def test_tries_native_first(self):
        """Native parser should be tried before XML."""
        response = {
            "message": {
                "tool_calls": [{"function": {"name": "native_tool", "arguments": "{}"}}],
                "content": '<tools>{"name": "xml_tool", "arguments": {}}</tools>'
            }
        }
        parser = CompositeParser()
        parsed = parser.parse(response)
        
        # Should find native tool and return (not both)
        assert any(tc.name == "native_tool" for tc in parsed.tool_calls)

    def test_falls_back_to_xml(self):
        """Should use XML parser when native is empty."""
        response = {"message": {"content": '<tools>{"name": "xml_only", "arguments": {}}</tools>'}}
        parser = CompositeParser()
        parsed = parser.parse(response)
        
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "xml_only"

    def test_handles_no_tool_calls(self):
        """Should return empty tool_calls for regular content."""
        response = {"message": {"content": "Just a regular response"}}
        parser = CompositeParser()
        parsed = parser.parse(response)
        
        assert parsed.tool_calls == []
        assert parsed.content == "Just a regular response"

    def test_handles_malformed_gracefully(self):
        """Should not crash on malformed input."""
        # Multi-line malformed JSON - parser can't extract valid tool call
        response = {"message": {"content": "<tools>{\nbroken\njson\n}</tools>"}}
        parser = CompositeParser()
        parsed = parser.parse(response)  # Should not raise
        
        assert parsed.tool_calls == []

    def test_handles_empty_response(self):
        """Should handle empty/None responses gracefully."""
        parser = CompositeParser()
        
        # Empty dict
        parsed1 = parser.parse({})
        assert parsed1.tool_calls == []
        
        # None in message
        parsed2 = parser.parse({"message": None})
        assert parsed2.tool_calls == []

    def test_can_parse_always_true(self):
        """Composite parser should always return True for can_parse."""
        parser = CompositeParser()
        assert parser.can_parse({}) is True
        assert parser.can_parse(None) is True
        assert parser.can_parse("string") is True
