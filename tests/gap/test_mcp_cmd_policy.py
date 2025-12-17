import os
from unittest.mock import patch

import pytest

# Helper to clear lru_cache of is_isolated_environment
from llmc_mcp.isolation import is_isolated_environment
from llmc_mcp.tools.cmd import run_cmd


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure clean environment for each test."""
    # Save original env
    old_env = os.environ.copy()

    # Clear isolation markers
    vars_to_clear = [
        "LLMC_ISOLATED",
        "KUBERNETES_SERVICE_HOST",
        "container",
        "NSJAIL",
        "FIREJAIL",
    ]
    for v in vars_to_clear:
        if v in os.environ:
            del os.environ[v]

    # Clear cache
    is_isolated_environment.cache_clear()

    yield

    # Restore
    os.environ.clear()
    os.environ.update(old_env)
    is_isolated_environment.cache_clear()


def test_run_cmd_fails_without_isolation(tmp_path):
    """Verify run_cmd fails when not in an isolated environment."""
    # Ensure we are definitely not isolated
    # We rely on clean_env fixture clearing vars.
    # Also assume we are not running this test in a real docker container
    # (or if we are, we can't easily fail this test without mocking Path check)

    with patch("pathlib.Path.exists", return_value=False):  # Mock /.dockerenv check
        result = run_cmd("ls", cwd=tmp_path)

        assert result.success is False
        assert "requires an isolated environment" in result.error
        assert result.exit_code == -1


def test_run_cmd_respects_blacklist(tmp_path):
    """Verify run_cmd respects a custom blacklist."""
    # Enable isolation to bypass that check
    os.environ["LLMC_ISOLATED"] = "1"
    is_isolated_environment.cache_clear()

    custom_blacklist = ["ls", "rm"]

    # 1. Blocked command
    result = run_cmd("ls -la", cwd=tmp_path, blacklist=custom_blacklist)
    assert result.success is False
    assert "blacklisted" in result.error

    # 2. Allowed command
    result = run_cmd("echo hello", cwd=tmp_path, blacklist=custom_blacklist)
    assert result.success is True
    assert "hello" in result.stdout
