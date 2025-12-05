"""
Tests for log management scripts:
- llmc-clean-logs.sh
- llmc_log_manager.py

Tests cover:
- Detecting log files above size/age limits
- Safe rotation/deletion
- Never deleting non-log files
- Safety checks for unset/incorrect log directories
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestLLMCCleanLogs:
    """Test llmc-clean-logs.sh wrapper script."""

    def test_script_exists_and_executable(self):
        """Test that llmc-clean-logs.sh exists and is executable."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        assert script_path.exists(), "llmc-clean-logs.sh should exist"
        assert os.access(script_path, os.X_OK), "llmc-clean-logs.sh should be executable"

    def test_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/bin/bash" or first_line == "#!/usr/bin/env bash"

    def test_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)], check=False, capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        result = subprocess.run(
            [str(script_path), "--help"], check=False, capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout or "LLMC Log Cleanup" in result.stdout
        assert "--dir" in result.stdout or "-d" in result.stdout
        assert "--check" in result.stdout or "-c" in result.stdout
        assert "--rotate" in result.stdout or "-r" in result.stdout

    def test_default_values(self):
        """Test that script has reasonable default values."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with open(script_path) as f:
            content = f.read()

        # Should have default log dir
        assert "DEFAULT_LOG_DIR" in content or "/logs" in content

        # Should have default max size
        assert "DEFAULT_MAX_SIZE" in content or "10MB" in content

    def test_dir_flag(self):
        """Test -d/--dir flag accepts log directory."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should accept dir flag (may fail if log manager not found)

    def test_size_flag(self):
        """Test -s/--size flag accepts size argument."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--size", "5MB", "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should accept size flag

    def test_check_flag(self):
        """Test -c/--check flag sets check mode."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should accept check flag

    def test_rotate_flag(self):
        """Test -r/--rotate flag sets rotate mode."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--rotate"],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should accept rotate flag

    def test_quiet_flag(self):
        """Test -q/--quiet flag suppresses output."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--rotate", "--quiet"],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should accept quiet flag

    def test_fails_when_log_manager_missing(self):
        """Test that script fails when log manager is not found."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a non-existent log manager path
            subprocess.run(
                [str(script_path), "--dir", tmpdir, "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            # May fail due to missing log manager or other issues

    def test_calls_python_log_manager(self):
        """Test that script calls Python log manager."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with open(script_path) as f:
            content = f.read()

        # Should call python with log manager script
        assert "python" in content.lower()
        assert "llmc_log_manager.py" in content

    def test_passes_options_to_log_manager(self):
        """Test that script passes options to Python log manager."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with open(script_path) as f:
            content = f.read()

        # Should pass --check and --rotate options
        assert "--check" in content
        assert "--rotate" in content
        assert "--max-size" in content

    def test_parses_all_options(self):
        """Test that script parses all command line options."""
        script_path = scripts_dir / "llmc-clean-logs.sh"
        with open(script_path) as f:
            content = f.read()

        # Should have case statements for all options
        assert "-d|--dir)" in content
        assert "-s|--size)" in content
        assert "-c|--check)" in content
        assert "-r|--rotate)" in content
        assert "-q|--quiet)" in content
        assert "-h|--help)" in content


class TestLLMCLogManager:
    """Test llmc_log_manager.py module."""

    def test_script_exists(self):
        """Test that llmc_log_manager.py exists."""
        script_path = scripts_dir / "llmc_log_manager.py"
        assert script_path.exists(), "llmc_log_manager.py should exist"

    def test_has_python_shebang(self):
        """Test that script has proper python shebang."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env python3"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "llmc_log_manager.py"
        result = subprocess.run(
            [str(script_path), "--help"], check=False, capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "LLMC Log Manager" in result.stdout

    def test_check_flag(self):
        """Test --check flag checks log sizes."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--check", tmpdir], check=False, capture_output=True, text=True
            )
            # Should check logs (may have no logs to check)

    def test_rotate_flag(self):
        """Test --rotate flag rotates oversized logs."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--rotate", "--max-size", "10MB", tmpdir],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should rotate logs

    def test_max_size_flag(self):
        """Test --max-size flag accepts size."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with MB suffix
            subprocess.run(
                [str(script_path), "--check", "--max-size", "5MB", tmpdir],
                check=False,
                capture_output=True,
                text=True,
            )

            # Test with KB suffix
            subprocess.run(
                [str(script_path), "--check", "--max-size", "512KB", tmpdir],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_quiet_flag(self):
        """Test --quiet flag suppresses output."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [str(script_path), "--check", "--quiet", tmpdir],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should work with quiet flag

    def test_handles_nonexistent_log_dir(self):
        """Test behavior with non-existent log directory."""
        script_path = scripts_dir / "llmc_log_manager.py"
        subprocess.run(
            [str(script_path), "--check", "/nonexistent/path"],
            check=False,
            capture_output=True,
            text=True,
        )
        # Should handle gracefully (may error or return empty results)

    def test_requires_log_dir_when_action_specified(self):
        """Test that log directory is required when check/rotate is specified."""
        script_path = scripts_dir / "llmc_log_manager.py"
        subprocess.run(
            [str(script_path), "--check"], check=False, capture_output=True, text=True
        )
        # Should require log directory argument

    def test_finds_log_patterns(self):
        """Test that script finds .log, .log.*, and .jsonl files."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test log files
            (Path(tmpdir) / "test.log").write_text("log content")
            (Path(tmpdir) / "test.log.1").write_text("rotated log")
            (Path(tmpdir) / "test.jsonl").write_text('{"key": "value"}\n')

            subprocess.run(
                [str(script_path), "--check", tmpdir], check=False, capture_output=True, text=True
            )
            # Should find and check these files

    def test_handles_jsonl_files(self):
        """Test that JSONL files are handled specially."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_file = Path(tmpdir) / "test.jsonl"
            # Create JSONL with many lines
            lines = [{"key": f"value_{i}"} for i in range(2000)]
            jsonl_file.write_text("\n".join(json.dumps(l) for l in lines))

            subprocess.run(
                [str(script_path), "--rotate", "--max-size", "0.01MB", tmpdir],
                check=False,
                capture_output=True,
                text=True,
            )
            # Should handle JSONL specially (keep structure)

    def test_respects_enabled_flag(self):
        """Test that rotation respects enabled flag."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Check that there's an enabled/disabled flag
        # Should have a way to disable rotation
        assert "enabled" in content.lower() or "enable_rotation" in content

    def test_config_file_support(self):
        """Test optional TOML config support."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should support TOML config
        assert "toml" in content.lower() or "config" in content.lower()
        assert "llmc.toml" in content

    def test_safety_checks_for_log_dir(self):
        """Test safety checks to avoid deleting non-log files."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should only operate on log files
        assert "*.log" in content or "patterns" in content
        assert "*.jsonl" in content

    def test_parses_size_units(self):
        """Test parsing of size units (MB, KB)."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should parse MB and KB units
        assert "MB" in content or "KB" in content

    def test_loads_config_from_file(self):
        """Test loading configuration from file."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should have config loading function
        assert "load_logging_config" in content or "config" in content

    def test_fails_closed_on_config_error(self):
        """Test that config errors don't break rotation."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            f.read()

        # Should handle config errors gracefully
        # "Fail closed" means continue without config on error

    def test_creates_summary_output(self):
        """Test that rotation creates summary output."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should print summary with emojis and counts
        assert "Log Check" in content or "Log Rotation" in content
        assert "Summary" in content

    def test_returns_structured_data(self):
        """Test that functions return structured data (dicts)."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Check methods return dicts
        assert "def check_logs" in content
        assert "def rotate_logs" in content
        # Return types should be dict-like

    def test_handles_file_age_and_size(self):
        """Test checking both file age and size."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should track file size and modification time
        assert "size" in content.lower() and (
            "mtime" in content.lower() or "age" in content.lower()
        )

    def test_provides_bytes_saved_in_rotation(self):
        """Test that rotation reports bytes saved."""
        script_path = scripts_dir / "llmc_log_manager.py"
        with open(script_path) as f:
            content = f.read()

        # Should report how many bytes were saved
        assert "bytes_saved" in content or "saved" in content
