"""MCP configuration loader - reads from llmc.toml with ENV overrides."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class McpServerConfig:
    """Server transport settings."""
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "info"


@dataclass
class McpAuthConfig:
    """Authentication settings."""
    mode: str = "none"  # "none" | "token"
    header: str = "X-LLMC-Token"
    token_env: str = "LLMC_MCP_TOKEN"


@dataclass
class McpToolsConfig:
    """Tool access settings."""
    allowed_roots: list[str] = field(default_factory=lambda: ["."])
    enable_run_cmd: bool = False
    run_cmd_allowlist: list[str] = field(
        default_factory=lambda: ["bash", "sh", "rg", "grep", "cat", "ls", "python"]
    )
    read_timeout: int = 10
    exec_timeout: int = 30


@dataclass
class McpRagConfig:
    """RAG adapter settings."""
    jit_context_enabled: bool = True
    default_scope: str = "repo"
    top_k: int = 3
    token_budget: int = 600


@dataclass
class McpLimitsConfig:
    """Request/response limits."""
    max_request_bytes: int = 262144
    max_response_bytes: int = 1048576
    rate_limit_rps: int = 10
    concurrency_per_token: int = 8


@dataclass
class McpObservabilityConfig:
    """Observability settings (M4)."""
    enabled: bool = False
    log_format: str = "json"  # "json" | "text"
    log_level: str = "info"
    include_correlation_id: bool = True
    # Metrics (stdio: in-memory only; HTTP: prometheus endpoint)
    metrics_enabled: bool = False
    metrics_path: str = "/metrics"
    # Token audit CSV
    csv_token_audit_enabled: bool = False
    csv_path: str = "./artifacts/token_audit.csv"
    # Retention (0 = forever)
    retention_days: int = 0


@dataclass
class McpConfig:
    """Root MCP configuration."""
    enabled: bool = True
    config_version: str = "v0"
    server: McpServerConfig = field(default_factory=McpServerConfig)
    auth: McpAuthConfig = field(default_factory=McpAuthConfig)
    tools: McpToolsConfig = field(default_factory=McpToolsConfig)
    rag: McpRagConfig = field(default_factory=McpRagConfig)
    limits: McpLimitsConfig = field(default_factory=McpLimitsConfig)
    observability: McpObservabilityConfig = field(default_factory=McpObservabilityConfig)


def _get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dict value."""
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key, default)
        if data is default:
            return default
    return data


def _apply_env_overrides(cfg: McpConfig) -> McpConfig:
    """Apply environment variable overrides. ENV beats TOML."""
    # LLMC_MCP_ENABLED
    if os.getenv("LLMC_MCP_ENABLED"):
        cfg.enabled = os.getenv("LLMC_MCP_ENABLED", "").lower() in ("1", "true", "yes")
    
    # LLMC_MCP_LOG_LEVEL
    if os.getenv("LLMC_MCP_LOG_LEVEL"):
        cfg.server.log_level = os.getenv("LLMC_MCP_LOG_LEVEL", cfg.server.log_level)
    
    # LLMC_MCP_ALLOWED_ROOTS (comma-separated)
    if os.getenv("LLMC_MCP_ALLOWED_ROOTS"):
        cfg.tools.allowed_roots = os.getenv("LLMC_MCP_ALLOWED_ROOTS", "").split(",")
    
    # Observability overrides (M4)
    if os.getenv("LLMC_MCP_OBS_ENABLED"):
        cfg.observability.enabled = os.getenv("LLMC_MCP_OBS_ENABLED", "").lower() in ("1", "true", "yes")
    if os.getenv("LLMC_MCP_OBS_LOG_FORMAT"):
        cfg.observability.log_format = os.getenv("LLMC_MCP_OBS_LOG_FORMAT", cfg.observability.log_format)
    if os.getenv("LLMC_MCP_OBS_CSV_ENABLED"):
        cfg.observability.csv_token_audit_enabled = os.getenv("LLMC_MCP_OBS_CSV_ENABLED", "").lower() in ("1", "true", "yes")
    if os.getenv("LLMC_MCP_OBS_CSV_PATH"):
        cfg.observability.csv_path = os.getenv("LLMC_MCP_OBS_CSV_PATH", cfg.observability.csv_path)
    
    return cfg


def load_config(config_path: str | Path | None = None) -> McpConfig:
    """
    Load MCP config from llmc.toml with ENV overrides.
    
    Precedence: ENV → TOML → defaults
    
    Args:
        config_path: Path to llmc.toml. If None, searches:
            1. LLMC_CONFIG env var
            2. LLMC_ROOT/llmc.toml
            3. ./llmc.toml
    
    Returns:
        McpConfig dataclass with merged settings.
    """
    # Find config file
    if config_path is None:
        if os.getenv("LLMC_CONFIG"):
            config_path = Path(os.getenv("LLMC_CONFIG"))
        elif os.getenv("LLMC_ROOT"):
            config_path = Path(os.getenv("LLMC_ROOT")) / "llmc.toml"
        else:
            config_path = Path("llmc.toml")
    else:
        config_path = Path(config_path)
    
    # Start with defaults
    cfg = McpConfig()
    
    # Load TOML if exists
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        
        mcp_data = data.get("mcp", {})
        
        # Top-level
        cfg.enabled = mcp_data.get("enabled", cfg.enabled)
        cfg.config_version = mcp_data.get("config_version", cfg.config_version)
        
        # Server
        srv = mcp_data.get("server", {})
        cfg.server.transport = srv.get("transport", cfg.server.transport)
        cfg.server.host = srv.get("host", cfg.server.host)
        cfg.server.port = srv.get("port", cfg.server.port)
        cfg.server.log_level = srv.get("log_level", cfg.server.log_level)
        
        # Auth
        auth = mcp_data.get("auth", {})
        cfg.auth.mode = auth.get("mode", cfg.auth.mode)
        cfg.auth.header = auth.get("header", cfg.auth.header)
        cfg.auth.token_env = auth.get("token_env", cfg.auth.token_env)
        
        # Tools
        tools = mcp_data.get("tools", {})
        cfg.tools.allowed_roots = tools.get("allowed_roots", cfg.tools.allowed_roots)
        cfg.tools.enable_run_cmd = tools.get("enable_run_cmd", cfg.tools.enable_run_cmd)
        cfg.tools.run_cmd_allowlist = tools.get("run_cmd_allowlist", cfg.tools.run_cmd_allowlist)
        cfg.tools.read_timeout = tools.get("read_timeout", cfg.tools.read_timeout)
        cfg.tools.exec_timeout = tools.get("exec_timeout", cfg.tools.exec_timeout)
        
        # RAG
        rag = mcp_data.get("rag", {})
        cfg.rag.jit_context_enabled = rag.get("jit_context_enabled", cfg.rag.jit_context_enabled)
        cfg.rag.default_scope = rag.get("default_scope", cfg.rag.default_scope)
        cfg.rag.top_k = rag.get("top_k", cfg.rag.top_k)
        cfg.rag.token_budget = rag.get("token_budget", cfg.rag.token_budget)
        
        # Limits
        limits = mcp_data.get("limits", {})
        cfg.limits.max_request_bytes = limits.get("max_request_bytes", cfg.limits.max_request_bytes)
        cfg.limits.max_response_bytes = limits.get("max_response_bytes", cfg.limits.max_response_bytes)
        
        # Observability (M4)
        obs = mcp_data.get("observability", {})
        cfg.observability.enabled = obs.get("enabled", cfg.observability.enabled)
        cfg.observability.log_format = obs.get("log_format", cfg.observability.log_format)
        cfg.observability.log_level = obs.get("log_level", cfg.observability.log_level)
        cfg.observability.include_correlation_id = obs.get("include_correlation_id", cfg.observability.include_correlation_id)
        cfg.observability.metrics_enabled = obs.get("metrics_enabled", cfg.observability.metrics_enabled)
        cfg.observability.metrics_path = obs.get("metrics_path", cfg.observability.metrics_path)
        cfg.observability.csv_token_audit_enabled = obs.get("csv_token_audit_enabled", cfg.observability.csv_token_audit_enabled)
        cfg.observability.csv_path = obs.get("csv_path", cfg.observability.csv_path)
        cfg.observability.retention_days = obs.get("retention_days", cfg.observability.retention_days)
    
    # Apply ENV overrides (highest precedence)
    cfg = _apply_env_overrides(cfg)
    
    return cfg
