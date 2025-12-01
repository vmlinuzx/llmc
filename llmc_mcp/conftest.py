"""Pytest fixtures for LLMC MCP."""

import os
import pytest
from pathlib import Path

@pytest.fixture
def mock_te_env(monkeypatch):
    """Set up standard TE environment variables."""
    monkeypatch.setenv("LLMC_TE_AGENT_ID", "test-agent")
    monkeypatch.setenv("LLMC_TE_SESSION_ID", "test-session")
    monkeypatch.setenv("LLMC_TE_MODEL", "test-model")
    # Backwards compat
    monkeypatch.setenv("TE_AGENT_ID", "test-agent")
    monkeypatch.setenv("TE_SESSION_ID", "test-session")
    monkeypatch.setenv("TE_MODEL", "test-model")

@pytest.fixture
def temp_llmc_repo(tmp_path):
    """Create a minimal LLMC repo structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "llmc.toml").touch()
    (repo / ".git").mkdir()
    return repo
