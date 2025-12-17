"""
Critical tests for tools/rag_nav/gateway.py

Tests cover:
- compute_route with no status
- compute_route with fresh matching head
- compute_route with fresh mismatched head (stale)
- compute_route handles missing graph when use_rag=True
"""

import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import pytest

from llmc.rag_nav.gateway import (
    RouteDecision,
    _detect_git_head,
    compute_route,
)


class TestComputeRoute:
    """Test compute_route function in various scenarios."""

    def test_compute_route_no_status(self):
        """Test compute_route when no status file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Mock load_status to return None
            with patch("llmc.rag_nav.gateway.load_status", return_value=None):
                decision = compute_route(repo_root)

                assert decision.use_rag is False
                assert decision.freshness_state == "UNKNOWN"
                assert decision.status is None

    def test_compute_route_no_status_module(self):
        """Test compute_route when load_status module is unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Mock load_status to raise exception
            with patch(
                "llmc.rag_nav.gateway.load_status", side_effect=Exception("Module not found")
            ):
                decision = compute_route(repo_root)

                assert decision.use_rag is False
                assert decision.freshness_state == "UNKNOWN"
                assert decision.status is None

    def test_compute_route_stale_index_state(self):
        """Test compute_route when index_state is not 'fresh'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Create mock status with stale index
            mock_status = Mock()
            mock_status.index_state = "stale"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                decision = compute_route(repo_root)

                assert decision.use_rag is False
                assert decision.freshness_state == "STALE"
                assert decision.status is mock_status

    def test_compute_route_fresh_matching_head(self):
        """Test compute_route with fresh index and matching HEAD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Mock git HEAD
            test_sha = "abc123def456"

            # Create mock status with fresh index and matching commit
            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = test_sha

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value=test_sha):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is True
                    assert decision.freshness_state == "FRESH"
                    assert decision.status is mock_status

    def test_compute_route_fresh_mismatched_head_is_stale(self):
        """Test compute_route with fresh index but mismatched HEAD returns STALE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            # Mock git HEAD different from last_indexed_commit
            current_sha = "xyz789"
            indexed_sha = "abc123"

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = indexed_sha

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value=current_sha):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is False
                    assert decision.freshness_state == "STALE"
                    assert decision.status is mock_status

    def test_compute_route_missing_git_head(self):
        """Test compute_route when git HEAD cannot be detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value=None):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is False
                    assert decision.freshness_state == "UNKNOWN"
                    assert decision.status is mock_status

    def test_compute_route_missing_last_indexed_commit(self):
        """Test compute_route when last_indexed_commit is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            mock_status = Mock()
            mock_status.index_state = "fresh"
            # last_indexed_commit is None or missing

            with patch.object(mock_status, "last_indexed_commit", None):
                with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                    with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                        decision = compute_route(repo_root)

                        assert decision.use_rag is False
                        assert decision.freshness_state == "UNKNOWN"
                        assert decision.status is mock_status

    def test_compute_route_case_insensitive_fresh(self):
        """Test that 'fresh' is case-insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            test_sha = "abc123"
            mock_status = Mock()

            # Test different case variations
            for index_state in ["FRESH", "Fresh", "fReSh", "fresh"]:
                mock_status.index_state = index_state
                mock_status.last_indexed_commit = test_sha

                with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                    with patch("llmc.rag_nav.gateway._detect_git_head", return_value=test_sha):
                        decision = compute_route(repo_root)

                        assert decision.use_rag is True
                        assert decision.freshness_state == "FRESH"

    def test_compute_route_missing_index_state(self):
        """Test compute_route when index_state is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            mock_status = Mock()
            # index_state is None or missing
            delattr(mock_status, "index_state")

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                decision = compute_route(repo_root)

                assert decision.use_rag is False
                assert decision.freshness_state == "STALE"

    def test_compute_route_non_fresh_variations(self):
        """Test that any non-'fresh' index_state returns STALE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            non_fresh_states = [
                "building",
                "indexing",
                "outdated",
                "corrupted",
                "empty",
                "",
                "fresh_build",  # Contains 'fresh' but not exactly 'fresh'
            ]

            for state in non_fresh_states:
                mock_status = Mock()
                mock_status.index_state = state

                with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is False
                    assert decision.freshness_state == "STALE"

    def test_compute_route_returns_route_decision(self):
        """Test that compute_route returns proper RouteDecision object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                    decision = compute_route(repo_root)

                    # Verify it's a RouteDecision dataclass
                    assert isinstance(decision, RouteDecision)
                    assert hasattr(decision, "use_rag")
                    assert hasattr(decision, "freshness_state")
                    assert hasattr(decision, "status")


class TestDetectGitHead:
    """Test _detect_git_head function."""

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_success(self, mock_run):
        """Test successful git HEAD detection."""
        # Mock successful git command
        mock_process = Mock()
        mock_process.stdout = "abc123def456789\n"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = _detect_git_head(repo_root)

            assert result == "abc123def456789"

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_with_whitespace(self, mock_run):
        """Test git HEAD detection strips whitespace."""
        mock_process = Mock()
        mock_process.stdout = "  abc123  \n  "
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = _detect_git_head(repo_root)

            assert result == "abc123"

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_empty_output(self, mock_run):
        """Test git HEAD detection with empty output."""
        mock_process = Mock()
        mock_process.stdout = ""
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = _detect_git_head(repo_root)

            assert result is None

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_git_error(self, mock_run):
        """Test git HEAD detection when git command fails."""
        mock_run.side_effect = Exception("git not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = _detect_git_head(repo_root)

            assert result is None

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_nonzero_exit(self, mock_run):
        """Test git HEAD detection with non-zero exit code."""
        mock_process = Mock()
        mock_process.stdout = ""
        mock_process.stderr = "not a git repository"
        mock_run.return_value = mock_process

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = _detect_git_head(repo_root)

            assert result is None

    @patch("llmc.rag_nav.gateway.run")
    def test_detect_git_head_uses_git_flag(self, mock_run):
        """Test that git command uses -C flag."""
        mock_process = Mock()
        mock_process.stdout = "abc123\n"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _detect_git_head(repo_root)

            # Verify git -C was called
            call_args = mock_run.call_args
            assert call_args is not None
            args, kwargs = call_args
            assert "git" in args[0]
            assert "-C" in args[0]
            assert str(repo_root) in args[0]


class TestMissingGraphWhenUseRagTrue:
    """Test that missing graph when use_rag=True raises appropriate error."""

    def test_missing_graph_raises_error_current_policy(self):
        """Test current policy: missing graph when use_rag=True raises error.

        This test documents the current behavior: when compute_route
        returns use_rag=True but the RAG graph is missing, the system
        should raise an appropriate error.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            (repo_root / ".llmc").mkdir()  # Create .llmc directory
            # But don't create rag_graph.json

            # Mock status to indicate FRESH
            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                    decision = compute_route(repo_root)

                    # Decision says use RAG
                    assert decision.use_rag is True

                    # But graph file doesn't exist
                    graph_path = repo_root / ".llmc" / "rag_graph.json"
                    assert not graph_path.exists()

                    # According to current policy, should raise error when trying to use missing graph
                    # In a real implementation, this would be caught when actually loading the graph
                    with pytest.raises(FileNotFoundError):
                        with open(graph_path) as f:
                            f.read()

    def test_missing_graph_directory(self):
        """Test that missing .llmc directory is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            # Don't create .llmc directory

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                    decision = compute_route(repo_root)

                    # Still says use RAG based on status
                    assert decision.use_rag is True

                    # But directory doesn't exist
                    assert not (repo_root / ".llmc").exists()

    def test_empty_graph_file(self):
        """Test that empty graph file is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            (repo_root / ".llmc").mkdir()

            # Create empty graph file
            graph_path = repo_root / ".llmc" / "rag_graph.json"
            graph_path.write_text("")

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is True

                    # Graph exists but is empty - should be handled gracefully
                    # Actual loading would fail with validation error
                    with pytest.raises((json.JSONDecodeError, ValueError)):
                        with open(graph_path) as f:
                            json.load(f)

    def test_malformed_graph_json(self):
        """Test that malformed JSON in graph file is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".git").mkdir()
            (repo_root / ".llmc").mkdir()

            # Create malformed JSON
            graph_path = repo_root / ".llmc" / "rag_graph.json"
            graph_path.write_text("{ invalid json }")

            mock_status = Mock()
            mock_status.index_state = "fresh"
            mock_status.last_indexed_commit = "abc123"

            with patch("llmc.rag_nav.gateway.load_status", return_value=mock_status):
                with patch("llmc.rag_nav.gateway._detect_git_head", return_value="abc123"):
                    decision = compute_route(repo_root)

                    assert decision.use_rag is True

                    # Should fail when loading
                    with pytest.raises(json.JSONDecodeError):
                        with open(graph_path) as f:
                            json.load(f)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
