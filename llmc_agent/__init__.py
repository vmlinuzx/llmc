"""llmc_agent - AI coding assistant integrated with LLMC RAG."""

__version__ = "0.1.0"
__author__ = "David Carroll"

from llmc_agent.agent import Agent, AgentResponse, run_agent
from llmc_agent.config import Config, load_config
from llmc_agent.session import Session, SessionManager

__all__ = [
    "Agent",
    "AgentResponse",
    "Config",
    "Session",
    "SessionManager",
    "load_config",
    "run_agent",
]
