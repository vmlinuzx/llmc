"""Configuration loading for llmc_agent.

Config precedence (lowest to highest):
1. Built-in defaults (in code)
2. ~/.llmc/agent.toml (user global)
3. ./.llmc/agent.toml (repo local)
4. llmc.toml [agent] section (if exists)
5. Environment variables (LLMC_AGENT_*)
6. CLI flags
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Any

# tomli for Python < 3.11, else tomllib
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class OllamaConfig:
    """Ollama backend configuration."""

    # Available servers:
    # url: str = "http://localhost:11434"  # Local Ollama
    url: str = "http://athena:11434"  # Athena LLM shitbox
    timeout: int = 120
    temperature: float = 0.7
    num_ctx: int = 8192


@dataclass
class RAGConfig:
    """RAG (LLMC) configuration."""

    enabled: bool = True
    max_results: int = 5
    min_score: float = 0.3
    include_summary: bool = True


@dataclass
class OpenAIConfig:
    """OpenAI-compatible backend configuration.
    
    Works with llama.cpp server, vLLM, text-generation-inference,
    and other OpenAI-compatible endpoints.
    """

    url: str = "http://athena:8080/v1"  # llama-server on Athena
    api_key: str | None = None
    timeout: int = 300
    temperature: float = 0.6
    model: str | None = None  # If set, overrides agent.model for this backend


@dataclass
class LiteLLMConfig:
    """LiteLLM backend configuration.
    
    LiteLLM provides a unified interface to 100+ LLM providers.
    Use this for simplified multi-provider support.
    
    Model format: "provider/model" (e.g., "ollama_chat/qwen3", "openai/gpt-4o")
    """

    enabled: bool = True  # LiteLLM is now the default backend
    model: str = "ollama_chat/qwen3-next-80b"  # LiteLLM format
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 120.0
    num_retries: int = 3



@dataclass
class AgentConfig:
    """Agent configuration."""

    # Available providers:
    # provider: str = "ollama"  # Ollama API (default)
    # provider: str = "openai"  # OpenAI-compatible API (llama-server, vLLM, etc.)
    provider: str = "ollama"  # Default backend
    
    # Available models:
    # model: str = "qwen3:4b-instruct"  # Fast, local, limited capability
    # model: str = "hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q8_K_XL"  # Athena 30B coder
    # model: str = "gpt-oss-120b-F16.gguf"  # GPT-OSS-120B on llama-server (use provider=openai)
    model: str = "qwen3-next-80b-nothink"  # Boxxie: 80B MoE @ 32 t/s on Athena
    context_budget: int = 6000
    response_reserve: int = 1024
    timeout: int = 300


@dataclass
class SessionConfig:
    """Session configuration."""

    storage: str = "~/.llmc"  # Changed from ~/.bx
    timeout_hours: float = 4.0
    max_history_tokens: int = 4096


@dataclass
class UIConfig:
    """UI configuration."""

    color: str = "auto"
    quiet: bool = False
    show_tokens: bool = True
    show_sources: bool = True


@dataclass
class ToolsConfig:
    """Tool calling format configuration for UTP.
    
    Controls how tool calls are parsed from LLM responses and
    how tool definitions/results are formatted for the provider.
    """

    definition_format: str = "openai"  # How to send tool definitions
    call_parser: str = "auto"  # "auto" | "openai" | "anthropic" | "qwen"
    result_format: str = "openai"  # How to format tool results


@dataclass
class Config:
    """Root configuration."""

    agent: AgentConfig = field(default_factory=AgentConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    litellm: LiteLLMConfig = field(default_factory=LiteLLMConfig)

    @classmethod
    def load(cls, config_path: str | None = None) -> Config:
        """
        Load agent configuration from multiple sources with a defined precedence.

        The configuration is loaded in the following order (lowest to highest precedence):
        1.  **Built-in Defaults:** The default values defined in the dataclasses.
        2.  **User Global Config (`~/.llmc/agent.toml`):** User-specific settings that apply
            across all projects.
        3.  **Repo-Local Config (`./.llmc/agent.toml`):** Project-specific settings that
            are shared among collaborators.
        4.  **Main `llmc.toml`:** The `[agent]` section of the root `llmc.toml` is loaded,
            allowing for centralized configuration of all components.
        5.  **Environment Variables:** `LLMC_AGENT_*` or legacy `BX_*` variables can be
            used to override any settings from the configuration files.
        6.  **CLI Flags:** Command-line arguments (processed in `llmc_agent.cli`) have the
            highest precedence.

        Args:
            config_path: An optional path to a specific configuration file to load. This
                file will be loaded with higher precedence than the standard files.

        Returns:
            A `Config` object with the merged configuration.
        """
        config = cls()

        # Load from files (lowest to highest priority)
        config_files = [
            Path.home() / ".llmc" / "agent.toml",  # 2. User global config
            Path.cwd() / ".llmc" / "agent.toml",   # 3. Repo-local config
            Path.cwd() / "llmc.toml",              # 4. Main llmc.toml [agent] section
        ]

        if config_path:
            config_files.append(Path(config_path))

        for path in config_files:
            if path.exists():
                config = _merge_config(config, _load_toml(path))

        # 5. Apply environment overrides
        config = _apply_env_overrides(config)

        # 6. CLI flags are applied in the CLI module.

        return config


def _load_toml(path: Path) -> dict[str, Any]:
    """Load TOML file."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _merge_config(config: Config, data: dict[str, Any]) -> Config:
    """Merge TOML data into config."""

    if "agent" in data:
        agent_data = data["agent"]
        if "provider" in agent_data:
            config.agent.provider = agent_data["provider"]
        if "model" in agent_data:
            config.agent.model = agent_data["model"]
        if "context_budget" in agent_data:
            config.agent.context_budget = agent_data["context_budget"]
        if "response_reserve" in agent_data:
            config.agent.response_reserve = agent_data["response_reserve"]
        if "timeout" in agent_data:
            config.agent.timeout = agent_data["timeout"]

    if "openai" in data:
        openai_data = data["openai"]
        if "url" in openai_data:
            config.openai.url = openai_data["url"]
        if "api_key" in openai_data:
            config.openai.api_key = openai_data["api_key"]
        if "timeout" in openai_data:
            config.openai.timeout = openai_data["timeout"]
        if "temperature" in openai_data:
            config.openai.temperature = openai_data["temperature"]
        if "model" in openai_data:
            config.openai.model = openai_data["model"]

    if "ollama" in data:
        ollama_data = data["ollama"]
        if "url" in ollama_data:
            config.ollama.url = ollama_data["url"]
        if "timeout" in ollama_data:
            config.ollama.timeout = ollama_data["timeout"]
        if "temperature" in ollama_data:
            config.ollama.temperature = ollama_data["temperature"]
        if "num_ctx" in ollama_data:
            config.ollama.num_ctx = ollama_data["num_ctx"]

    if "rag" in data:
        rag_data = data["rag"]
        if "enabled" in rag_data:
            config.rag.enabled = rag_data["enabled"]
        if "max_results" in rag_data:
            config.rag.max_results = rag_data["max_results"]
        if "min_score" in rag_data:
            config.rag.min_score = rag_data["min_score"]
        if "include_summary" in rag_data:
            config.rag.include_summary = rag_data["include_summary"]

    if "session" in data:
        session_data = data["session"]
        if "storage" in session_data:
            config.session.storage = session_data["storage"]
        if "timeout_hours" in session_data:
            config.session.timeout_hours = session_data["timeout_hours"]
        if "max_history_tokens" in session_data:
            config.session.max_history_tokens = session_data["max_history_tokens"]

    if "ui" in data:
        ui_data = data["ui"]
        if "color" in ui_data:
            config.ui.color = ui_data["color"]
        if "quiet" in ui_data:
            config.ui.quiet = ui_data["quiet"]
        if "show_tokens" in ui_data:
            config.ui.show_tokens = ui_data["show_tokens"]
        if "show_sources" in ui_data:
            config.ui.show_sources = ui_data["show_sources"]

    if "tools" in data:
        tools_data = data["tools"]
        if "definition_format" in tools_data:
            config.tools.definition_format = tools_data["definition_format"]
        if "call_parser" in tools_data:
            config.tools.call_parser = tools_data["call_parser"]
        if "result_format" in tools_data:
            config.tools.result_format = tools_data["result_format"]

    if "litellm" in data:
        litellm_data = data["litellm"]
        if "enabled" in litellm_data:
            config.litellm.enabled = litellm_data["enabled"]
        if "model" in litellm_data:
            config.litellm.model = litellm_data["model"]
        if "api_key" in litellm_data:
            config.litellm.api_key = litellm_data["api_key"]
        if "api_base" in litellm_data:
            config.litellm.api_base = litellm_data["api_base"]
        if "temperature" in litellm_data:
            config.litellm.temperature = litellm_data["temperature"]
        if "max_tokens" in litellm_data:
            config.litellm.max_tokens = litellm_data["max_tokens"]
        if "timeout" in litellm_data:
            config.litellm.timeout = litellm_data["timeout"]
        if "num_retries" in litellm_data:
            config.litellm.num_retries = litellm_data["num_retries"]

    return config


def _apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides.

    Pattern: LLMC_AGENT_SECTION_KEY, e.g., LLMC_AGENT_MODEL, LLMC_OLLAMA_URL
    Also supports legacy BX_* vars for compatibility.
    """

    env_map = {
        # New LLMC_AGENT_* style
        "LLMC_AGENT_PROVIDER": ("agent", "provider"),
        "LLMC_AGENT_MODEL": ("agent", "model"),
        "LLMC_AGENT_CONTEXT_BUDGET": ("agent", "context_budget", int),
        "LLMC_OLLAMA_URL": ("ollama", "url"),
        "LLMC_OLLAMA_TIMEOUT": ("ollama", "timeout", int),
        "LLMC_OPENAI_URL": ("openai", "url"),
        "LLMC_OPENAI_TIMEOUT": ("openai", "timeout", int),
        "LLMC_RAG_ENABLED": (
            "rag",
            "enabled",
            lambda x: x.lower() in ("true", "1", "yes"),
        ),
        "LLMC_LITELLM_ENABLED": (
            "litellm",
            "enabled",
            lambda x: x.lower() in ("true", "1", "yes"),
        ),
        "LLMC_LITELLM_MODEL": ("litellm", "model"),
        # Legacy BX_* style (for backwards compat)
        "BX_PROVIDER": ("agent", "provider"),
        "BX_MODEL": ("agent", "model"),
        "BX_AGENT_MODEL": ("agent", "model"),
        "BX_CONTEXT_BUDGET": ("agent", "context_budget", int),
        "BX_OLLAMA_URL": ("ollama", "url"),
        "BX_TIMEOUT": ("ollama", "timeout", int),
        "BX_RAG_ENABLED": (
            "rag",
            "enabled",
            lambda x: x.lower() in ("true", "1", "yes"),
        ),
    }

    for env_var, spec in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            section = spec[0]
            key = spec[1]
            converter = spec[2] if len(spec) > 2 else str

            section_obj = getattr(config, section)
            try:
                setattr(section_obj, key, converter(value))
            except (ValueError, TypeError):
                pass  # Ignore invalid env values

    return config


# Convenience function
def load_config(config_path: str | None = None) -> Config:
    """Load configuration."""
    return Config.load(config_path)
