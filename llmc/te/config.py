"""
Configuration for Tool Envelope.

Loads from [tool_envelope] section of llmc.toml.
Agent budgets auto-tune output to caller's context window.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


def _find_repo_root(start: Path | None = None) -> Path:
    """Find the git repository root."""
    start = start or Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return current


@lru_cache
def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    """Load llmc.toml configuration."""
    root = repo_root or _find_repo_root()
    path = root / "llmc.toml"
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


# Default agent budgets (output chars, roughly tokens * 4)
DEFAULT_AGENT_BUDGETS = {
    "gemini-shell": 900_000,
    "claude-dc": 180_000,
    "qwen-local": 28_000,
    "human-cli": 50_000,
    "unknown": 16_000,
}


@dataclass
class TeConfig:
    """Tool Envelope configuration."""

    enabled: bool = True
    workspace_root: Path = field(default_factory=Path.cwd)
    respect_gitignore: bool = True
    allow_outside_root: bool = False

    # Telemetry
    telemetry_enabled: bool = True
    telemetry_path: str = ".llmc/te_telemetry.jsonl"

    # Grep defaults
    grep_preview_matches: int = 10
    grep_max_output_chars: int = 20_000
    grep_timeout_ms: int = 5_000

    # Cat defaults
    cat_preview_lines: int = 50
    cat_max_output_chars: int = 30_000

    # Agent budgets
    agent_budgets: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_AGENT_BUDGETS))


def get_te_config(repo_root: Path | None = None) -> TeConfig:
    """Load TE configuration from llmc.toml."""
    cfg = load_config(repo_root)
    te_cfg = cfg.get("tool_envelope", {})

    root = repo_root or _find_repo_root()

    # Build config with defaults
    workspace = te_cfg.get("workspace", {})
    telemetry = te_cfg.get("telemetry", {})
    grep = te_cfg.get("grep", {})
    cat = te_cfg.get("cat", {})
    budgets = te_cfg.get("agent_budgets", {})

    return TeConfig(
        enabled=te_cfg.get("enabled", True),
        workspace_root=Path(workspace.get("root", root)),
        respect_gitignore=workspace.get("respect_gitignore", True),
        allow_outside_root=workspace.get("allow_outside_root", False),
        telemetry_enabled=telemetry.get("enabled", True),
        telemetry_path=telemetry.get("path", ".llmc/te_telemetry.jsonl"),
        grep_preview_matches=grep.get("preview_matches", 10),
        grep_max_output_chars=grep.get("max_output_chars", 20_000),
        grep_timeout_ms=grep.get("timeout_ms", 5_000),
        cat_preview_lines=cat.get("preview_lines", 50),
        cat_max_output_chars=cat.get("max_output_chars", 30_000),
        agent_budgets={**DEFAULT_AGENT_BUDGETS, **budgets},
    )


def get_output_budget(agent_id: str | None, repo_root: Path | None = None) -> int:
    """Get output budget for an agent (respects TE_AGENT_ID env)."""
    agent = agent_id or os.getenv("TE_AGENT_ID", "unknown")
    cfg = get_te_config(repo_root)
    return cfg.agent_budgets.get(agent, cfg.agent_budgets.get("unknown", 16_000))
