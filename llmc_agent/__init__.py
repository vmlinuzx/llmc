"""llmc_agent - AI coding assistant integrated with LLMC RAG."""

__version__ = "0.1.0"
__author__ = "David Carroll"

from llmc_agent.agent import Agent, AgentResponse, ToolCall, run_agent
from llmc_agent.config import Config, load_config
from llmc_agent.session import Session, SessionManager
from llmc_agent.tools import Tool, ToolRegistry, ToolTier, detect_intent_tier

__all__ = [
    "Agent",
    "AgentResponse",
    "Config",
    "Session",
    "SessionManager",
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "ToolTier",
    "detect_intent_tier",
    "load_config",
    "run_agent",
]
