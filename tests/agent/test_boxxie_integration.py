"""Integration test for Boxxie tool calling with UTP."""

from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestBoxxieIntegration:
    """Integration tests for UTP with Boxxie (Qwen XML format)."""

    @pytest.mark.asyncio
    async def test_boxxie_xml_tool_call_parsed(self):
        """Test that XML tool calls from Boxxie are parsed correctly."""
        from llmc_agent.format import FormatNegotiator
        
        # Simulate Boxxie response with XML tool call (as Qwen does)
        mock_response = {
            "message": {
                "content": 'I will search for that.\n\n<tools>\n{"name": "search_code", "arguments": {"query": "authentication"}}\n</tools>',
                "tool_calls": None,  # No native tool calls - Boxxie uses XML
            },
            "done": True,
            "eval_count": 50,
            "prompt_eval_count": 100,
        }
        
        negotiator = FormatNegotiator()
        parser = negotiator.get_call_parser()
        parsed = parser.parse(mock_response)
        
        # Should find the XML tool call
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].arguments == {"query": "authentication"}
        assert "I will search" in parsed.content

    @pytest.mark.asyncio
    async def test_boxxie_multiple_xml_tool_calls(self):
        """Test parsing multiple XML tool calls in one response."""
        from llmc_agent.format import FormatNegotiator
        
        mock_response = {
            "message": {
                "content": '''Let me search and read the file.

<tools>
{"name": "search_code", "arguments": {"query": "auth"}}
</tools>

<tools>
{"name": "read_file", "arguments": {"path": "auth.py"}}
</tools>''',
            },
        }
        
        negotiator = FormatNegotiator()
        parser = negotiator.get_call_parser()
        parsed = parser.parse(mock_response)
        
        assert len(parsed.tool_calls) == 2
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[1].name == "read_file"

    @pytest.mark.asyncio
    async def test_native_format_still_works(self):
        """Test that native OpenAI format still works alongside XML."""
        from llmc_agent.format import FormatNegotiator
        
        # Standard OpenAI response format
        mock_response = {
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_abc123",
                    "function": {
                        "name": "search_code",
                        "arguments": '{"query": "auth"}'
                    }
                }]
            },
            "done": True,
        }
        
        negotiator = FormatNegotiator()
        parser = negotiator.get_call_parser()
        parsed = parser.parse(mock_response)
        
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].id == "call_abc123"

    @pytest.mark.asyncio
    async def test_agent_format_negotiator_initialization(self):
        """Test that Agent initializes format_negotiator correctly."""
        from llmc_agent.agent import Agent
        from llmc_agent.config import Config
        
        # Create minimal config
        config = Config()
        
        # Mock the backends to avoid network calls
        with patch('llmc_agent.agent.OllamaBackend'), \
             patch('llmc_agent.agent.LLMCBackend'):
            agent = Agent(config)
            
            assert hasattr(agent, 'format_negotiator')
            assert agent.format_negotiator is not None
            
            # Should be able to get a parser
            parser = agent.format_negotiator.get_call_parser()
            assert parser is not None


@pytest.mark.integration
class TestAdaptersIntegration:
    """Integration tests for UTP adapters."""

    def test_result_adapter_formats_correctly(self):
        """Test that OpenAIResultAdapter creates valid tool messages."""
        from llmc_agent.format.adapters import OpenAIResultAdapter
        from llmc_agent.format.types import ToolCall, ToolResult
        
        adapter = OpenAIResultAdapter()
        call = ToolCall(name="search", arguments={"q": "test"}, id="call_123")
        result = ToolResult(
            call_id="call_123",
            tool_name="search",
            result={"matches": ["file1.py", "file2.py"]}
        )
        
        msg = adapter.format_result(call, result)
        
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_123"
        assert "matches" in msg["content"] or "file1.py" in msg["content"]

    def test_definition_adapter_formats_tools(self):
        """Test that OpenAIDefinitionAdapter formats tool definitions."""
        from llmc_agent.format.adapters import OpenAIDefinitionAdapter
        
        # Simulate internal tool format
        tools = [{
            "name": "search_code",
            "description": "Search for code patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }]
        
        adapter = OpenAIDefinitionAdapter()
        result = adapter.format_tools(tools)
        
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search_code"
