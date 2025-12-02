"""
LinuxOps configuration.

Dataclasses for process limits, feature flags, etc.
Loaded from [mcp.linux_ops] section in llmc.toml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LinuxOpsProcessLimits:
    """Process management limits and safety settings."""

    max_procs_per_session: int = 4
    max_procs_total: int = 32
    default_timeout_sec: int = 60
    max_timeout_sec: int = 600
    allow_kill_other_users: bool = False


@dataclass
class LinuxOpsFeatureFlags:
    """Feature toggles for LinuxOps capabilities."""

    fs_enabled: bool = True
    proc_enabled: bool = True
    repl_enabled: bool = True
    system_enabled: bool = True


@dataclass
class LinuxOpsRoots:
    """Allowed filesystem roots."""

    allowed_roots: list[str] = field(default_factory=list)
    enforce_roots: bool = True


@dataclass
class LinuxOpsConfig:
    """Root LinuxOps configuration."""

    roots: LinuxOpsRoots = field(default_factory=LinuxOpsRoots)
    process_limits: LinuxOpsProcessLimits = field(default_factory=LinuxOpsProcessLimits)
    features: LinuxOpsFeatureFlags = field(default_factory=LinuxOpsFeatureFlags)


def load_linux_ops_config(toml_data: dict[str, Any]) -> LinuxOpsConfig:
    """
    Load LinuxOps config from parsed TOML data.

    Expected structure:
        [mcp.linux_ops.roots]
        allowed_roots = ["~", "~/src"]
        enforce_roots = true

        [mcp.linux_ops.process_limits]
        allow_kill_other_users = false

        [mcp.linux_ops.features]
        proc_enabled = true
    """
    linux_ops = toml_data.get("mcp", {}).get("linux_ops", {})

    # Roots
    roots_data = linux_ops.get("roots", {})
    roots = LinuxOpsRoots(
        allowed_roots=roots_data.get("allowed_roots", []),
        enforce_roots=roots_data.get("enforce_roots", True),
    )

    # Process limits
    proc_data = linux_ops.get("process_limits", {})
    process_limits = LinuxOpsProcessLimits(
        max_procs_per_session=proc_data.get("max_procs_per_session", 4),
        max_procs_total=proc_data.get("max_procs_total", 32),
        default_timeout_sec=proc_data.get("default_timeout_sec", 60),
        max_timeout_sec=proc_data.get("max_timeout_sec", 600),
        allow_kill_other_users=proc_data.get("allow_kill_other_users", False),
    )

    # Feature flags
    feat_data = linux_ops.get("features", {})
    features = LinuxOpsFeatureFlags(
        fs_enabled=feat_data.get("fs_enabled", True),
        proc_enabled=feat_data.get("proc_enabled", True),
        repl_enabled=feat_data.get("repl_enabled", True),
        system_enabled=feat_data.get("system_enabled", True),
    )

    return LinuxOpsConfig(
        roots=roots,
        process_limits=process_limits,
        features=features,
    )
