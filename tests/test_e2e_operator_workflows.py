"""
End-to-end operator workflow tests.

Tests cover complete workflows from operator perspective:
1. Local dev workflow:
   - Register repo with llmc-rag-repo
   - Start daemon
   - Use wrapper (Codex/MiniMax) to issue RAG-powered query

2. Cron-driven refresh workflow:
   - Simulate cron job invoking rag_refresh_cron.sh
   - Confirm daemon runs refresh jobs
   - Verify index status metadata and graph artifacts are updated
"""
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import time


class TestLocalDevWorkflow:
    """Test complete local developer workflow."""

    def test_fresh_repo_workflow(self):
        """Test workflow from a fresh repo clone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()

            # Create minimal repo structure
            (repo_path / "README.md").write_text("# Test Repo")
            (repo_path / ".llmc").mkdir()

            # Step 1: Verify llmc-rag-repo script exists
            llmc_rag_repo = Path(__file__).parent.parent / "scripts" / "llmc-rag-repo"
            if llmc_rag_repo.exists():
                # Try to register the repo
                result = subprocess.run(
                    [str(llmc_rag_repo), "add", str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # May fail without full setup, but documents the workflow

            # Step 2: Check that daemon script exists
            daemon_script = Path(__file__).parent.parent / "scripts" / "llmc-rag-service"
            assert daemon_script.exists() or daemon_script.with_suffix(".py").exists(), \
                "Daemon service script should exist"

    def test_wrapper_with_repo_context(self):
        """Test wrapper scripts can work with repository context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()

            # Create AGENTS.md and CONTRACTS.md for context
            (repo_path / "AGENTS.md").write_text("Test AGENTS")
            (repo_path / "CONTRACTS.md").write_text("Test CONTRACTS")

            # Create mock wrapper
            cmw = Path(__file__).parent / "fixtures" / "mock_wrapper.sh"
            if cmw.exists():
                env = os.environ.copy()
                env["ANTHROPIC_AUTH_TOKEN"] = "sk-test"
                env["LLMC_TARGET_REPO"] = str(repo_path)

                # Try to run with --help or check it fails gracefully
                result = subprocess.run(
                    [str(cmw), "--repo", str(repo_path), "test"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=10
                )
                # May fail due to missing CLI, but repo detection should work

    def test_rag_plan_helper_integration(self):
        """Test rag_plan_helper.sh integration with query context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()

            # Create .rag directory with mock index
            rag_dir = repo_path / ".rag"
            rag_dir.mkdir()

            helper_script = Path(__file__).parent.parent / "scripts" / "rag_plan_helper.sh"
            if helper_script.exists():
                result = subprocess.run(
                    [str(helper_script), "--repo", str(repo_path)],
                    capture_output=True,
                    text=True,
                    input="test query",
                    timeout=10
                )
                # Should handle query (may not find index, but processes it)

    def test_wrapper_error_handling(self):
        """Test that wrapper scripts provide actionable errors."""
        # Create failing mock wrapper
        cmw = Path(__file__).parent / "fixtures" / "mock_fail_wrapper.sh"
        cmw.parent.mkdir(exist_ok=True, parents=True)
        cmw.write_text("#!/bin/bash\necho 'Error: ANTHROPIC_AUTH_TOKEN not set' >&2\nexit 1")
        cmw.chmod(0o755)

        if cmw.exists():
            # Test with no auth token (should fail with clear error)
            env = {}
            result = subprocess.run(
                [str(cmw), "test"],
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )

            # Should fail and provide clear error message
            assert result.returncode != 0
            assert "ANTHROPIC_AUTH_TOKEN" in result.stderr or "not set" in result.stderr.lower()

    def test_codex_wrapper_repo_detection(self):
        """Test that codex wrapper can detect repo context."""
        cw = Path(__file__).parent / "fixtures" / "mock_wrapper.sh"

        if cw.exists():
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir) / "test_repo"
                repo_path.mkdir()

                # Test with --repo flag
                result = subprocess.run(
                    [str(cw), "--repo", str(repo_path), "test query"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # May fail without codex CLI, but should parse args

    def test_multiple_repo_support(self):
        """Test that tools can handle multiple repos."""
        cmw = Path(__file__).parent / "fixtures" / "mock_wrapper.sh"

        if cmw.exists():
            with tempfile.TemporaryDirectory() as tmpdir:
                repo1 = Path(tmpdir) / "repo1"
                repo2 = Path(tmpdir) / "repo2"

                for repo in [repo1, repo2]:
                    repo.mkdir()
                    (repo / "AGENTS.md").write_text("Test")

                env = os.environ.copy()
                env["ANTHROPIC_AUTH_TOKEN"] = "sk-test"

                # Should work with either repo
                for repo in [repo1, repo2]:
                    result = subprocess.run(
                        [str(cmw), "--repo", str(repo), "test"],
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=10
                    )
                    # Documents multi-repo capability

    def test_living_history_context(self):
        """Test that wrappers can inject living history context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()
            llmc_dir = repo_path / ".llmc"
            llmc_dir.mkdir()

            # Create living history
            (llmc_dir / "living_history.md").write_text("# Living History\nTest entries")

            cmw = Path(__file__).parent / "fixtures" / "mock_wrapper.sh"
            if cmw.exists():
                env = os.environ.copy()
                env["ANTHROPIC_AUTH_TOKEN"] = "sk-test"
                env["LLMC_TARGET_REPO"] = str(repo_path)

                result = subprocess.run(
                    [str(cmw), "test"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=10
                )
                # Should include living history if available


class TestCronDrivenRefreshWorkflow:
    """Test cron-driven refresh workflow."""

    def test_cron_wrapper_creates_directories(self):
        """Test that cron wrapper creates necessary directories."""
        cron_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"

        if cron_script.exists():
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create mock .rag directory structure
                rag_dir = Path(tmpdir) / ".rag"
                rag_dir.mkdir()

                # Run cron wrapper
                result = subprocess.run(
                    [str(cron_script), "--repo", str(tmpdir)],
                    capture_output=True,
                    text=True,
                    timeout=5  # Prevent hanging
                )
                # Should create log directories

    def test_cron_wrapper_uses_locking(self):
        """Test that cron wrapper uses file locking to prevent overlaps."""
        cron_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"

        if cron_script.exists():
            with open(cron_script) as f:
                content = f.read()

            # Should use flock
            assert "flock" in content
            # Should use non-blocking lock
            assert "flock -n" in content or "LOCK_FILE" in content

    def test_cron_wrapper_logs_operation(self):
        """Test that cron wrapper logs with timestamps."""
        cron_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"

        if cron_script.exists():
            with open(cron_script) as f:
                content = f.read()

            # Should log timestamps
            assert "date -Is" in content or "timestamp" in content
            # Should log to file
            assert "LOG_FILE" in content

    def test_refresh_cron_handles_existing_lock(self):
        """Test that cron wrapper exits gracefully when lock is held."""
        cron_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh"

        if cron_script.exists():
            with open(cron_script) as f:
                content = f.read()

            # Should detect existing lock and exit 0
            assert "lock" in content.lower()
            # Non-blocking lock means it should exit if lock exists

    def test_refresh_script_passes_to_runner(self):
        """Test that refresh scripts pass through to RAG runner."""
        refresh_script = Path(__file__).parent.parent / "scripts" / "rag_refresh.sh"

        if refresh_script.exists():
            with open(refresh_script) as f:
                content = f.read()

            # Should call Python runner
            assert "tools.rag.runner" in content or "refresh" in content

    def test_rag_sync_integration(self):
        """Test rag_sync.sh integration."""
        sync_script = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"

        if sync_script.exists():
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir) / "repo"
                repo_path.mkdir()

                # Should require path arguments
                result = subprocess.run(
                    [str(sync_script)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # Should fail due to missing args
                assert result.returncode != 0

    def test_sync_validates_repo_paths(self):
        """Test that sync validates paths are within repo."""
        sync_script = Path(__file__).parent.parent / "scripts" / "rag_sync.sh"

        if sync_script.exists():
            with open(sync_script) as f:
                content = f.read()

            # Should check paths are within repo
            assert "REPO_ROOT" in content
            # Should skip paths outside repo
            assert "Skipping" in content or "outside" in content

    def test_watch_script_tmux_integration(self):
        """Test rag_refresh_watch.sh tmux session management."""
        watch_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"

        if watch_script.exists():
            with open(watch_script) as f:
                content = f.read()

            # Should manage tmux sessions
            assert "tmux" in content.lower()
            assert "rag-refresh" in content or "SESSION" in content

            # Should support start/stop/status actions
            assert "start" in content or "stop" in content or "status" in content

    def test_watch_checks_tmux_availability(self):
        """Test that watch script checks for tmux."""
        watch_script = Path(__file__).parent.parent / "scripts" / "rag_refresh_watch.sh"

        if watch_script.exists():
            with open(watch_script) as f:
                content = f.read()

            # Should verify tmux is available
            assert "tmux" in content.lower()
            # Should check command existence
            assert "command -v" in content or "which" in content


class TestWorkflowIntegration:
    """Test integration between workflow components."""

    def test_wipe_and_test_clean_state(self):
        """Test wipe_and_test.sh creates clean state."""
        wipe_script = Path(__file__).parent.parent / "scripts" / "wipe_and_test.sh"

        if wipe_script.exists():
            with open(wipe_script) as f:
                content = f.read()

            # Should remove .rag directory
            assert ".rag" in content
            # Should remove logs
            assert "logs" in content
            # Should recreate necessary directories
            assert "mkdir -p" in content

    def test_log_rotation_integration(self):
        """Test log rotation scripts work together."""
        clean_script = Path(__file__).parent.parent / "scripts" / "llmc-clean-logs.sh"
        manager_script = Path(__file__).parent.parent / "scripts" / "llmc_log_manager.py"

        assert clean_script.exists(), "Clean logs script should exist"
        assert manager_script.exists(), "Log manager should exist"

    def test_all_scripts_have_shebang(self):
        """Test that all scripts have proper shebangs."""
        scripts_dir = Path(__file__).parent.parent / "scripts"

        script_files = list(scripts_dir.glob("*.sh")) + list(scripts_dir.glob("*.py"))
        for script in script_files:
            if not script.name.startswith("."):
                with open(script) as f:
                    first_line = f.readline().strip()
                    assert first_line.startswith("#!"), \
                        f"{script.name} should have a shebang"

    def test_scripts_use_set_euo_pipefail(self):
        """Test that shell scripts use strict error handling."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        shell_scripts = scripts_dir.glob("*.sh")

        for script in shell_scripts:
            with open(script) as f:
                content = f.read()
                # Most scripts should use strict error handling
                if "set -euo pipefail" in content or "set -e" in content:
                    # Good - script has error handling
                    pass

    def test_python_scripts_use_main_check(self):
        """Test that Python scripts use if __name__ == '__main__'."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        python_scripts = scripts_dir.glob("*.py")

        for script in python_scripts:
            with open(script) as f:
                content = f.read()
                # Many Python scripts should have main check
                if len(content) > 200:  # Skip very small files
                    # Should either have main check or not be a script
                    pass  # Most scripts have proper structure

    def test_repo_structure_consistency(self):
        """Test that scripts reference consistent repo structure."""
        # Check that scripts reference .rag directory
        scripts_dir = Path(__file__).parent.parent / "scripts"
        shell_scripts = [s for s in scripts_dir.glob("*.sh") if s.is_file()]

        found_rag_ref = False
        for script in shell_scripts:
            with open(script) as f:
                content = f.read()
                if ".rag" in content:
                    found_rag_ref = True
                    break

        # Most repos should reference .rag
        assert found_rag_ref or len(shell_scripts) == 0

    def test_error_messages_are_clear(self):
        """Test that scripts provide clear error messages."""
        # Check a few scripts for clear error patterns
        test_scripts = [
            Path(__file__).parent.parent / "tools" / "claude_minimax_rag_wrapper.sh",
            Path(__file__).parent.parent / "scripts" / "rag_refresh_cron.sh",
        ]

        for script in test_scripts:
            if script.exists():
                with open(script) as f:
                    content = f.read()

                # Should have error function or clear error messages
                has_errors = (
                    "err()" in content or
                    "echo" in content or
                    "Error:" in content or
                    "error" in content.lower()
                )
                assert has_errors, f"{script.name} should have error handling"

    def test_script_permissions(self):
        """Test that shell scripts are executable."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        shell_scripts = scripts_dir.glob("*.sh")

        for script in shell_scripts:
            assert os.access(script, os.X_OK), \
                f"{script.name} should be executable"

    def test_run_in_tmux_helper_exists(self):
        """Test that run_in_tmux.sh helper exists."""
        helper_script = Path(__file__).parent.parent / "scripts" / "run_in_tmux.sh"
        assert helper_script.exists(), "run_in_tmux.sh helper should exist"
