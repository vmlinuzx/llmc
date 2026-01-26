"""RLM Configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from llmc.core import find_repo_root, load_config


@dataclass
class RLMConfig:
    """Configuration for RLM sessions."""
    
    # Model selection
    root_model: str = "ollama_chat/qwen3-next-80b"
    sub_model: str = "ollama_chat/qwen3-next-80b"
    
    # Budget limits
    max_session_budget_usd: float = 1.00
    max_tokens_per_session: int = 500_000
    max_subcall_depth: int = 5
    soft_limit_percentage: float = 0.80
    
    # Timeouts
    code_timeout_seconds: int = 30
    session_timeout_seconds: int = 300  # 5 minutes
    
    # Context limits
    max_context_chars: int = 1_000_000
    max_print_chars: int = 10_000
    max_turns: int = 20
    
    # LLM params
    root_temperature: float = 0.1
    root_max_tokens: int = 4096
    sub_temperature: float = 0.1
    sub_max_tokens: int = 1024
    
    # Token estimation
    chars_per_token: int = 4
    token_safety_multiplier: float = 1.2
    
    # Sandbox
    sandbox_backend: str = "process"
    security_mode: str = "permissive"  # or "restrictive"
    blocked_builtins: frozenset[str] = field(default_factory=lambda: frozenset({
        'open', 'exec', 'eval', 'compile', '__import__',
        'input', 'breakpoint', 'exit', 'quit',
    }))
    allowed_modules: frozenset[str] = field(default_factory=lambda: frozenset({
        'json', 're', 'math', 'collections', 'itertools',
        'functools', 'operator', 'string', 'textwrap',
        'datetime', 'copy', 'typing', 'dataclasses',
    }))
    
    # Logging
    trace_enabled: bool = True
    
    # Trace preview limits
    prompt_preview_chars: int = 200
    response_preview_chars: int = 200
    match_preview_chars: int = 200
    stdout_preview_chars: int = 2000

    def validate(self) -> None:
        """Validate config values. Raises ValueError on invalid config."""
        if self.max_session_budget_usd < 0:
            raise ValueError("max_session_budget_usd cannot be negative")
        if self.code_timeout_seconds < 1:
            raise ValueError("code_timeout_seconds must be >= 1")
        if self.chars_per_token < 1:
            raise ValueError("chars_per_token must be >= 1")
        if self.max_subcall_depth < 0:
            raise ValueError("max_subcall_depth cannot be negative")


def load_rlm_config(config_path: Path | None = None) -> RLMConfig:
    """Load RLM config from llmc.toml [rlm] section.
    
    Uses LLMC's standard config discovery via find_repo_root().
    """
    if config_path:
        if config_path.is_file():
            with open(config_path, "rb") as f:
                full_config = tomllib.load(f)
        else:
            full_config = load_config(config_path)
    else:
        full_config = load_config(find_repo_root())
    
    rlm_data = full_config.get("rlm", {})
    return _parse_rlm_section(rlm_data)


def _parse_rlm_section(data: dict) -> RLMConfig:
    """Parse [rlm] section into RLMConfig, merging with defaults.
    
    Handles nested sections: budget, sandbox, llm.root, llm.sub, token_estimate, session, trace.
    """
    import dataclasses
    defaults = RLMConfig()
    
    # Extract all nested sections
    budget_data = data.pop("budget", {})
    sandbox_data = data.pop("sandbox", {})
    llm_data = data.pop("llm", {})
    token_estimate_data = data.pop("token_estimate", {})
    session_data = data.pop("session", {})
    trace_data = data.pop("trace", {})
    
    overrides = {}
    
    # [rlm.budget]
    if "max_session_budget_usd" in budget_data:
        overrides["max_session_budget_usd"] = budget_data["max_session_budget_usd"]
    if "max_session_tokens" in budget_data:
        overrides["max_tokens_per_session"] = budget_data["max_session_tokens"]
    elif "max_tokens_per_session" in budget_data:
        overrides["max_tokens_per_session"] = budget_data["max_tokens_per_session"]
    if "max_subcall_depth" in budget_data:
        overrides["max_subcall_depth"] = budget_data["max_subcall_depth"]
    if "soft_limit_percentage" in budget_data:
        overrides["soft_limit_percentage"] = budget_data["soft_limit_percentage"]
    
    # [rlm.llm.root] and [rlm.llm.sub]
    llm_root_data = llm_data.get("root", {})
    llm_sub_data = llm_data.get("sub", {})
    if "temperature" in llm_root_data:
        overrides["root_temperature"] = llm_root_data["temperature"]
    if "max_tokens" in llm_root_data:
        overrides["root_max_tokens"] = llm_root_data["max_tokens"]
    if "temperature" in llm_sub_data:
        overrides["sub_temperature"] = llm_sub_data["temperature"]
    if "max_tokens" in llm_sub_data:
        overrides["sub_max_tokens"] = llm_sub_data["max_tokens"]
    
    # [rlm.token_estimate]
    if "chars_per_token" in token_estimate_data:
        overrides["chars_per_token"] = token_estimate_data["chars_per_token"]
    if "safety_multiplier" in token_estimate_data:
        overrides["token_safety_multiplier"] = token_estimate_data["safety_multiplier"]
    
    # [rlm.session]
    if "max_turns" in session_data:
        overrides["max_turns"] = session_data["max_turns"]
    if "session_timeout_seconds" in session_data:
        overrides["session_timeout_seconds"] = session_data["session_timeout_seconds"]
    if "max_context_chars" in session_data:
        overrides["max_context_chars"] = session_data["max_context_chars"]
    if "max_output_chars" in session_data:
        overrides["max_print_chars"] = session_data["max_output_chars"]
    
    # [rlm.trace]
    if "enabled" in trace_data:
        overrides["trace_enabled"] = trace_data["enabled"]
    if "prompt_preview_chars" in trace_data:
        overrides["prompt_preview_chars"] = trace_data["prompt_preview_chars"]
    if "response_preview_chars" in trace_data:
        overrides["response_preview_chars"] = trace_data["response_preview_chars"]
    if "stdout_preview_chars" in trace_data:
        overrides["stdout_preview_chars"] = trace_data["stdout_preview_chars"]
    
    # [rlm.sandbox]
    if "backend" in sandbox_data:
        overrides["sandbox_backend"] = sandbox_data["backend"]
    if "security_mode" in sandbox_data:
        overrides["security_mode"] = sandbox_data["security_mode"]
    if "code_timeout_seconds" in sandbox_data:
        overrides["code_timeout_seconds"] = sandbox_data["code_timeout_seconds"]
    if "blocked_builtins" in sandbox_data:
        overrides["blocked_builtins"] = frozenset(sandbox_data["blocked_builtins"])
    if "allowed_modules" in sandbox_data:
        overrides["allowed_modules"] = frozenset(sandbox_data["allowed_modules"])
    
    # Handle remaining flat fields
    for field_name in RLMConfig.__dataclass_fields__:
        if field_name in data:
            overrides[field_name] = data[field_name]
    
    # Filter and apply
    valid_overrides = {
        k: v for k, v in overrides.items() 
        if k in RLMConfig.__dataclass_fields__
    }
    config = dataclasses.replace(defaults, **valid_overrides)
    config.validate()
    return config
