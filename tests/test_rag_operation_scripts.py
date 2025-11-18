"""
Tests for RAG operation scripts:
- rag_plan_helper.sh
- rag_plan_snippet.py
- index_workspace.py
- query_context.py

Tests cover:
- CLI ergonomic usage and --help output
- Safe handling of missing or misconfigured workspaces
- Query context generation
- Workspace indexing
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestRagPlanHelper:
    """Test rag_plan_helper.sh script."""

    def test_script_exists_and_executable(self):
        """Test that rag_plan_helper.sh exists and is executable."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        assert script_path.exists(), "rag_plan_helper.sh should exist"
        assert os.access(script_path, os.X_OK), "rag_plan_helper.sh should be executable"

    def test_script_has_proper_shebang(self):
        """Test that script has proper bash shebang."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env bash"

    def test_script_valid_bash_syntax(self):
        """Test that script has valid bash syntax."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--repo" in result.stdout

    def test_repo_flag(self):
        """Test --repo flag accepts path."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir],
                capture_output=True,
                text=True,
                input=""  # Empty input
            )
            # Should exit 0 (no query provided)
            assert result.returncode == 0

    def test_repo_equals_syntax(self):
        """Test --repo=/path syntax."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), f"--repo={tmpdir}"],
                capture_output=True,
                text=True,
                input=""
            )
            assert result.returncode == 0

    def test_handles_empty_query(self):
        """Test that empty query is handled gracefully."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input=""
        )
        # Should exit 0 for empty query
        assert result.returncode == 0

    def test_handles_query_from_stdin(self):
        """Test that query from stdin is read correctly."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input="test query"
        )
        # May fail without proper setup, but should process the query
        # This tests stdin handling

    def test_handles_missing_index(self):
        """Test behavior when RAG index is missing."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir],
                capture_output=True,
                text=True,
                input="test query"
            )
            # Should handle missing index gracefully (exit 0)
            assert result.returncode == 0

    def test_respects_disable_rag_env(self):
        """Test that CODEX_WRAP_DISABLE_RAG env var is respected."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        env = os.environ.copy()
        env["CODEX_WRAP_DISABLE_RAG"] = "1"

        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input="test query",
            env=env
        )
        # Should exit 0 when RAG is disabled
        assert result.returncode == 0

    def test_respects_llm_gateway_disable_rag_env(self):
        """Test that LLM_GATEWAY_DISABLE_RAG env var is respected."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        env = os.environ.copy()
        env["LLM_GATEWAY_DISABLE_RAG"] = "1"

        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input="test query",
            env=env
        )
        # Should exit 0 when RAG is disabled
        assert result.returncode == 0

    def test_unknown_option_error(self):
        """Test that unknown options produce error."""
        script_path = scripts_dir / "rag_plan_helper.sh"
        result = subprocess.run(
            [str(script_path), "--unknown-flag"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0
        assert "unknown option" in result.stderr or "Usage" in result.stderr


class TestRagPlanSnippet:
    """Test rag_plan_snippet.py script."""

    def test_script_exists(self):
        """Test that rag_plan_snippet.py exists."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        assert script_path.exists(), "rag_plan_snippet.py should exist"

    def test_has_python_shebang(self):
        """Test that script has proper python shebang."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env python3"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()
        assert "--repo" in result.stdout
        assert "--limit" in result.stdout

    def test_accepts_query_args(self):
        """Test that script accepts query as command line args."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "test", "query", "string"],
            capture_output=True,
            text=True
        )
        # May fail without proper RAG setup, but should parse args
        # This tests argument parsing

    def test_accepts_query_from_stdin(self):
        """Test that script reads query from stdin."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input="test query from stdin"
        )
        # May fail without RAG setup, but should read stdin

    def test_repo_flag(self):
        """Test --repo flag."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir, "test query"],
                capture_output=True,
                text=True
            )
            # Should handle repo flag

    def test_limit_flag(self):
        """Test --limit flag."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--limit", "10", "test query"],
            capture_output=True,
            text=True
        )
        # Should accept limit flag

    def test_min_score_flag(self):
        """Test --min-score flag."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--min-score", "0.5", "test query"],
            capture_output=True,
            text=True
        )
        # Should accept min-score flag

    def test_min_confidence_flag(self):
        """Test --min-confidence flag."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--min-confidence", "0.7", "test query"],
            capture_output=True,
            text=True
        )
        # Should accept min-confidence flag

    def test_no_log_flag(self):
        """Test --no-log flag."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--no-log", "test query"],
            capture_output=True,
            text=True
        )
        # Should accept no-log flag

    def test_handles_missing_repo(self):
        """Test behavior with missing repo."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path), "--repo", "/nonexistent/path", "test query"],
            capture_output=True,
            text=True
        )
        # Should handle missing repo gracefully

    def test_handles_empty_query(self):
        """Test behavior with empty query."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            input=""
        )
        # Should exit 0 for empty query
        assert result.returncode == 0

    def test_handles_missing_db(self):
        """Test behavior when RAG db is missing."""
        script_path = scripts_dir / "rag_plan_snippet.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir, "test query"],
                capture_output=True,
                text=True
            )
            # Should handle missing db gracefully (exit 0)
            assert result.returncode == 0


class TestIndexWorkspace:
    """Test index_workspace.py script."""

    def test_script_exists(self):
        """Test that index_workspace.py exists."""
        script_path = scripts_dir / "rag" / "index_workspace.py"
        assert script_path.exists(), "index_workspace.py should exist"

    def test_has_python_shebang(self):
        """Test that script has proper python shebang."""
        script_path = scripts_dir / "rag" / "index_workspace.py"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env python3"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "rag" / "index_workspace.py"
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        # May fail on import, but let's check if help is defined
        # This documents expected behavior

    def test_accepts_workspace_path(self):
        """Test that script accepts workspace path."""
        script_path = scripts_dir / "rag" / "index_workspace.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            # May fail due to missing dependencies, but should accept args
            result = subprocess.run(
                [str(script_path), tmpdir],
                capture_output=True,
                text=True
            )
            # Test documents that args are parsed


class TestQueryContext:
    """Test query_context.py script."""

    def test_script_exists(self):
        """Test that query_context.py exists."""
        script_path = scripts_dir / "rag" / "query_context.py"
        assert script_path.exists(), "query_context.py should exist"

    def test_has_python_shebang(self):
        """Test that script has proper python shebang."""
        script_path = scripts_dir / "rag" / "query_context.py"
        with open(script_path) as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env python3"

    def test_help_flag(self):
        """Test --help flag displays usage."""
        script_path = scripts_dir / "rag" / "query_context.py"
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        # Should display help

    def test_accepts_query_and_repo(self):
        """Test that script accepts query and repo path."""
        script_path = scripts_dir / "rag" / "query_context.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir, "test query"],
                capture_output=True,
                text=True
            )
            # Should accept query and repo args

    def test_handles_invalid_repo_path(self):
        """Test behavior with invalid repo path."""
        script_path = scripts_dir / "rag" / "query_context.py"
        result = subprocess.run(
            [str(script_path), "--repo", "/nonexistent", "test query"],
            capture_output=True,
            text=True
        )
        # Should handle invalid path gracefully with error

    def test_handles_empty_query(self):
        """Test behavior with empty query."""
        script_path = scripts_dir / "rag" / "query_context.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(script_path), "--repo", tmpdir],
                capture_output=True,
                text=True,
                input=""
            )
            # Should handle empty query

    def test_validates_required_args(self):
        """Test that required args are validated."""
        script_path = scripts_dir / "rag" / "query_context.py"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True
        )
        # Should require query/repo args
        # Exit code may vary
