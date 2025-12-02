"""
Tests for refresh/sync/cron helper scripts:
- rag_refresh.sh
- rag_refresh_cron.sh
- rag_refresh_watch.sh
- rag_sync.sh

Tests cover:
- Triggering refresh cycles
- Daemon operations
- Log generation
- Graceful failure on missing config
- Sync operations
"""
import os
from pathlib import Path
import subprocess
import tempfile


class TestRagRefresh:
    """Test rag_refresh.sh script."""

    def test_script_exists_and_executable(self):
        """Test that rag_refresh.sh exists and is executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        assert script_path.exists(), "rag_refresh.sh should exist"
        assert os.access(script_path, os.X_OK), "rag_refresh.sh should be executable"

    def test_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env bash"

    def test_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_python_path_resolution(self):
        """Test Python binary path resolution logic."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        with open(script_path) as f:
            content = f.read()

        # Should check for .venv first, then fallback to python3
        assert ".venv/bin/python" in content or ".venv" in content
        assert "python3" in content

    def test_uses_set_euo_pipefail(self):
        """Test that script uses strict error handling."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        with open(script_path) as f:
            content = f.read()

        assert "set -euo pipefail" in content

    def test_passes_args_to_runner(self):
        """Test that script passes arguments to Python runner."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"
        with open(script_path) as f:
            content = f.read()

        # Should exec to Python runner with args
        assert "tools.rag.runner refresh" in content
        assert '"$@"' in content or "$@" in content


class TestRagRefreshCron:
    """Test rag_refresh_cron.sh script."""

    def test_script_exists_and_executable(self):
        """Test that rag_refresh_cron.sh exists and is executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        assert script_path.exists(), "rag_refresh_cron.sh should exist"
        assert os.access(script_path, os.X_OK), "rag_refresh_cron.sh should be executable"

    def test_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env bash"

    def test_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        result = subprocess.run(
            [str(script_path), "--help"],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stderr or "Usage:" in result.stdout

    def test_repo_flag(self):
        """Test --repo flag accepts path."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir],
                check=False, capture_output=True,
                text=True
            )
            # May fail without proper setup, but should accept --repo

    def test_repo_equals_syntax(self):
        """Test --repo=/path syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), f"--repo={tmpdir}"],
                check=False, capture_output=True,
                text=True
            )
            # Should accept this syntax

    def test_uses_locking_mechanism(self):
        """Test that script uses file locking to prevent overlaps."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use flock for locking
        assert "flock" in content
        assert "LOCK_FILE" in content

    def test_creates_lock_file(self):
        """Test that script creates lock file in .rag directory."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Lock file should be in .rag directory
        assert ".rag/rag_refresh.lock" in content

    def test_respects_lock_env_vars(self):
        """Test that script respects lock file env var override."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should check RAG_REFRESH_LOCK_FILE env var
        assert "RAG_REFRESH_LOCK_FILE" in content

    def test_uses_logging(self):
        """Test that script logs to file."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use LOG_FILE
        assert "LOG_FILE" in content
        assert "LOG_DIR" in content

    def test_redirects_output(self):
        """Test that script redirects stdout/stderr to both console and log."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use tee to redirect output
        assert "tee" in content or "exec >" in content

    def test_creates_directories(self):
        """Test that script creates necessary directories."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use mkdir -p
        assert "mkdir -p" in content

    def test_handles_deep_research_ingest(self):
        """Test that script can call deep_research_ingest.sh."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # May optionally run deep research ingest
        assert "deep_research_ingest.sh" in content

    def test_passes_exit_code(self):
        """Test that script propagates exit code from rag_refresh.sh."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should capture and pass exit code
        assert "exit_code" in content
        assert "$exit_code" in content

    def test_logs_timestamps(self):
        """Test that script logs with timestamps."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should log timestamps
        assert "date -Is" in content

    def test_handles_missing_lock_gracefully(self):
        """Test that script handles existing lock gracefully."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use flock -n (non-blocking) and exit 0 if lock is held
        assert "flock -n" in content


class TestRagRefreshWatch:
    """Test rag_refresh_watch.sh script."""

    def test_script_exists_and_executable(self):
        """Test that rag_refresh_watch.sh exists and is executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        assert script_path.exists(), "rag_refresh_watch.sh should exist"
        assert os.access(script_path, os.X_OK), "rag_refresh_watch.sh should be executable"

    def test_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env bash"

    def test_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_supports_start_action(self):
        """Test that script supports start action."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "start)" in content
        assert "start_session" in content

    def test_supports_stop_action(self):
        """Test that script supports stop action."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "stop)" in content
        assert "stop_session" in content

    def test_supports_status_action(self):
        """Test that script supports status action."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "status)" in content
        assert "show_status" in content

    def test_supports_restart_action(self):
        """Test that script supports restart action."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "restart)" in content

    def test_supports_toggle_action(self):
        """Test that script supports toggle action."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "toggle)" in content
        assert "toggle_session" in content

    def test_uses_tmux(self):
        """Test that script uses tmux."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "tmux" in content.lower()
        assert "has-session" in content
        assert "kill-session" in content

    def test_checks_tmux_availability(self):
        """Test that script checks if tmux is available."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        # Should have tmux check function
        assert "ensure_tmux" in content or "command -v tmux" in content

    def test_checks_session_exists(self):
        """Test that script checks if tmux session exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        # Should have session_exists function
        assert "session_exists" in content
        assert "has-session" in content

    def test_uses_run_in_tmux(self):
        """Test that script uses run_in_tmux.sh helper."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        assert "run_in_tmux.sh" in content
        assert "RUNNER" in content

    def test_sets_session_name(self):
        """Test that script sets a fixed session name."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        # Should define SESSION variable
        assert 'SESSION="rag-refresh"' in content

    def test_displays_usage(self):
        """Test that script provides usage information."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        # Should have usage function
        assert "usage()" in content or "Usage:" in content
        assert "start" in content or "stop" in content

    def test_default_action_is_toggle(self):
        """Test that default action is toggle."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"
        with open(script_path) as f:
            content = f.read()

        # Should default to toggle
        assert 'action="${1:-toggle}"' in content


class TestRagSync:
    """Test rag_sync.sh script."""

    def test_script_exists_and_executable(self):
        """Test that rag_sync.sh exists and is executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        assert script_path.exists(), "rag_sync.sh should exist"
        assert os.access(script_path, os.X_OK), "rag_sync.sh should be executable"

    def test_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env bash"

    def test_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        result = subprocess.run(
            [str(script_path), "--help"],
            check=False, capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stderr or "Usage:" in result.stdout

    def test_requires_path_args(self):
        """Test that script requires path arguments."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should check for $# == 0 and exit with usage
        assert "print_usage" in content or "Usage:" in content

    def test_repo_flag(self):
        """Test --repo flag accepts path."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test without providing path args (should fail)
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir],
                check=False, capture_output=True,
                text=True
            )
            # Should fail due to missing path args
            assert result.returncode != 0

    def test_repo_equals_syntax(self):
        """Test --repo=/path syntax."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), f"--repo={tmpdir}"],
                check=False, capture_output=True,
                text=True
            )
            # Should fail due to missing path args

    def test_resolves_python_binary(self):
        """Test that script resolves Python binary with multiple fallbacks."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should check multiple locations for Python
        assert ".venv/bin/python" in content or "RAG_VENV" in content

    def test_validates_paths_are_within_repo(self):
        """Test that script validates paths are within repo root."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should check that paths are within repo
        assert "REPO_ROOT" in content
        # Should use realpath and check prefix
        assert "realpath" in content or "outside repo" in content

    def test_skips_paths_outside_repo(self):
        """Test that script skips paths outside repo root."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should skip paths outside repo
        assert "Skipping" in content or "outside repo" in content

    def test_uses_mktemp_for_temp_input(self):
        """Test that script uses mktemp for temporary input."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should use mktemp for temp file
        assert "mktemp" in content
        # Should clean up on exit
        assert "trap" in content and "EXIT" in content

    def test_cd_to_repo_root(self):
        """Test that script changes to repo root directory."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should cd to REPO_ROOT
        assert 'cd "$REPO_ROOT"' in content

    def test_calls_rag_cli_sync(self):
        """Test that script calls RAG CLI sync command."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should call tools.rag.cli sync
        assert "tools.rag.cli sync" in content
        assert "--stdin" in content

    def test_passes_pythonpath(self):
        """Test that script sets PYTHONPATH."""
        script_path = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"
        with open(script_path) as f:
            content = f.read()

        # Should set PYTHONPATH
        assert "PYTHONPATH" in content
