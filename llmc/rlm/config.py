"""RLM Configuration."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RLMConfig:
    """Configuration for RLM sessions."""
    
    # Model selection
    root_model: str = "ollama_chat/qwen3-next-80b"
    sub_model: str = "ollama_chat/qwen3-next-80b"
    
    # Budget limits
    max_session_budget_usd: float = 1.00
    max_tokens_per_session: int = 500_000
    max_subcall_depth: int = 5  # Honest naming: "sub-call depth" not "recursion"
    
    # Timeouts
    code_timeout_seconds: int = 30
    session_timeout_seconds: int = 300  # 5 minutes
    
    # Context limits
    max_context_chars: int = 1_000_000
    max_print_chars: int = 10_000
    
    # Sandbox
    sandbox_backend: str = "process"  # "process" or "restricted" (Tier 0 vs Tier -1)
    
    # Logging
    trace_enabled: bool = True


def load_rlm_config(config_path: str | None = None) -> RLMConfig:
    """Load RLM config from llmc.toml.
    
    For Phase 1, returns defaults. Phase 1.2 will read from [rlm] section.
    """
    # TODO: Read from llmc.toml [rlm] section
    return RLMConfig()
