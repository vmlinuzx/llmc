"""Context management for MCP sessions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass
class McpSessionContext:
    """Context for an MCP session (agent, session, model)."""
    
    agent_id: str
    session_id: str
    model: str

    @classmethod
    def from_env(cls) -> McpSessionContext:
        """Create context from current environment."""
        return cls(
            agent_id=os.getenv("LLMC_TE_AGENT_ID") or os.getenv("TE_AGENT_ID") or "unknown",
            session_id=os.getenv("LLMC_TE_SESSION_ID") or os.getenv("TE_SESSION_ID") or "unknown",
            model=os.getenv("LLMC_TE_MODEL") or os.getenv("TE_MODEL") or "unknown",
        )

    def to_env(self) -> dict[str, str]:
        """Convert context to environment variables."""
        return {
            "LLMC_TE_AGENT_ID": self.agent_id,
            "LLMC_TE_SESSION_ID": self.session_id,
            "LLMC_TE_MODEL": self.model,
            # Backwards compatibility
            "TE_AGENT_ID": self.agent_id,
            "TE_SESSION_ID": self.session_id,
            "TE_MODEL": self.model,
        }

    def attach_env(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        """Attach context to an existing environment dictionary."""
        new_env = dict(os.environ)
        if env:
            new_env.update(env)
        new_env.update(self.to_env())
        return new_env
