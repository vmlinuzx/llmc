
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from llmc_agent.tools import ToolRegistry, ToolTier, detect_intent_tier
from llmc_agent.agent import Agent
from llmc_agent.config import Config

class TestBoxxyAgent:
    
    def test_default_tier_is_walk(self):
        """Verify the agent starts at WALK tier by default (Boxxy change)."""
        registry = ToolRegistry()
        assert registry.current_tier == ToolTier.WALK
        
        # Verify read tools are available
        assert registry.is_tool_available("read_file")
        assert registry.is_tool_available("list_dir")
        
        # Verify write tools are NOT available yet
        assert not registry.is_tool_available("write_file")

    def test_intent_detection_naive(self):
        """Demonstrate that intent detection is naive."""
        # This is expected behavior for now, but good to document via test
        prompt = "Please do NOT edit any files, just look."
        tier = detect_intent_tier(prompt)
        assert tier == ToolTier.RUN, "Naive detection should trigger on 'edit' even if negated"

    def test_unlock_tier_monotonic(self):
        """Verify tier only goes up, never down."""
        registry = ToolRegistry(default_tier=ToolTier.WALK)
        assert registry.current_tier == ToolTier.WALK
        
        # Try to unlock CRAWL (should do nothing)
        registry.unlock_tier(ToolTier.CRAWL)
        assert registry.current_tier == ToolTier.WALK
        
        # Unlock RUN
        registry.unlock_tier(ToolTier.RUN)
        assert registry.current_tier == ToolTier.RUN
        
        # Try to go back to WALK (should do nothing)
        registry.unlock_tier(ToolTier.WALK)
        assert registry.current_tier == ToolTier.RUN

    @pytest.mark.asyncio
    async def test_agent_ask_with_tools_imports(self):
        """
        Verify that Agent.ask_with_tools runs without import errors.
        This targets the circular import and type hint issues seen in static analysis.
        """
        # Use real Config object instead of mock
        config = Config()
        config.rag.enabled = False
        config.agent.model = "test-model"
        
        # We still need to mock the backend calls to avoid network/system calls
        agent = Agent(config)
        agent.ollama = MagicMock()
        agent.ollama.generate_with_tools = AsyncMock(return_value=MagicMock(
            content="I am Boxxy",
            tokens_prompt=10,
            tokens_completion=10,
            tool_calls=[],
            model="test-model"
        ))
        
        # Mock load_system_prompt to avoid file I/O
        with patch("llmc_agent.agent.load_system_prompt", return_value="System Prompt"):
            response = await agent.ask_with_tools("Hello", session=None)
            
        assert response.content == "I am Boxxy"
        assert response.tier_used >= ToolTier.WALK # Should use at least default

    def test_tools_py_imports(self):
        """Verify tools.py imports don't crash."""
        from llmc_agent.tools import _make_read_file_tool
        tool = _make_read_file_tool(["."])
        assert tool.name == "read_file"

