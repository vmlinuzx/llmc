"""
Unit tests for the context gateway / compute_route function.

This module tests the routing decision logic that determines whether to use
RAG or fall back to deterministic methods based on freshness state.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

# Actual implementation
from tools.rag_nav.gateway import RouteDecision, compute_route
from tools.rag_nav.metadata import status_path


@pytest.mark.rag_freshness
class TestComputeRoute:
    """
    Test the context gateway routing decision logic.
    """

    def test_no_status_file(self, tmp_path: Path):
        """
        When no .llmc/rag_index_status.json exists:
        - use_rag should be False
        - freshness_state should be "UNKNOWN"
        """
        # Create a temporary repo without a status file
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        route = compute_route(repo_root)

        assert route.use_rag is False
        assert route.freshness_state == "UNKNOWN"

    def test_stale_index_state(self, tmp_path: Path):
        """
        When index_state is "stale":
        - use_rag should be False
        - freshness_state should be "STALE"
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create a stale status file
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            """{
                "repo": "test_repo",
                "index_state": "stale",
                "last_indexed_at": "2025-11-15T10:00:00Z",
                "last_indexed_commit": "abc123",
                "schema_version": "1.0"
            }"""
        )

        route = compute_route(repo_root)
        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_error_index_state(self, tmp_path: Path):
        """
        When index_state is "error":
        - use_rag should be False
        - freshness_state should be "STALE"
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create an error status file
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            """{
                "repo": "test_repo",
                "index_state": "error",
                "last_indexed_at": "2025-11-16T12:00:00Z",
                "last_indexed_commit": "abc123",
                "schema_version": "1.0",
                "last_error": "Database locked"
            }"""
        )

        route = compute_route(repo_root)
        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_rebuilding_index_state(self, tmp_path: Path):
        """
        When index_state is "rebuilding":
        - use_rag should be False
        - freshness_state should be "STALE" (or UNKNOWN? Code says STALE usually for non-fresh)
        """
        # Looking at implementation: if index_state != 'fresh', return STALE.
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create a rebuilding status file
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            """{
                "repo": "test_repo",
                "index_state": "rebuilding",
                "last_indexed_at": "2025-11-16T14:00:00Z",
                "last_indexed_commit": "abc123",
                "schema_version": "1.0"
            }"""
        )

        route = compute_route(repo_root)
        assert route.use_rag is False
        # Implementation says: if (index_state or "").lower() != "fresh": return ... freshness_state="STALE"
        assert route.freshness_state == "STALE"

    def test_fresh_index_head_mismatch(self, tmp_path: Path):
        """
        When index is fresh but HEAD commit differs:
        - use_rag should be False
        - freshness_state should be "STALE"
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create a status file with an old commit
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            """{
                "repo": "test_repo",
                "index_state": "fresh",
                "last_indexed_at": "2025-11-16T10:00:00Z",
                "last_indexed_commit": "old_commit_hash",
                "schema_version": "1.0"
            }"""
        )

        # Mock git to return a different HEAD
        with patch("tools.rag_nav.gateway._detect_git_head") as mock_git:
            mock_git.return_value = "new_commit_hash"
            route = compute_route(repo_root)

        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_fresh_index_head_match(self, tmp_path: Path):
        """
        When index is fresh and HEAD commit matches:
        - use_rag should be True
        - freshness_state should be "FRESH"
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create a status file with current commit
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            """{
                "repo": "test_repo",
                "index_state": "fresh",
                "last_indexed_at": "2025-11-16T10:00:00Z",
                "last_indexed_commit": "current_head",
                "schema_version": "1.0"
            }"""
        )

        # Mock git to return matching HEAD
        with patch("tools.rag_nav.gateway._detect_git_head") as mock_git:
            mock_git.return_value = "current_head"
            route = compute_route(repo_root)

        assert route.use_rag is True
        assert route.freshness_state == "FRESH"

    def test_malformed_status_file(self, tmp_path: Path):
        """
        When status file is malformed JSON:
        - use_rag should be False
        - freshness_state should be "UNKNOWN"
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create malformed JSON
        status_file = status_path(repo_root)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("{ invalid json ")

        route = compute_route(repo_root)
        assert route.use_rag is False
        assert route.freshness_state == "UNKNOWN"


@pytest.mark.rag_freshness
class TestRouteObject:
    """
    Test the Route object structure returned by compute_route.
    """

    def test_route_has_use_rag_field(self):
        """Route should have a use_rag boolean field."""
        route = RouteDecision(use_rag=True, freshness_state="FRESH", status=None)
        assert hasattr(route, "use_rag")
        assert isinstance(route.use_rag, bool)

    def test_route_has_freshness_state(self):
        """Route should have a freshness_state field of type FreshnessState."""
        route = RouteDecision(use_rag=True, freshness_state="FRESH", status=None)
        assert hasattr(route, "freshness_state")
        assert route.freshness_state in ("FRESH", "STALE", "UNKNOWN")

    def test_route_has_index_status(self):
        """Route should optionally include the IndexStatus used for the decision."""
        route = RouteDecision(use_rag=True, freshness_state="FRESH", status=None)
        assert hasattr(route, "status")


@pytest.mark.rag_freshness
class TestGitIntegration:
    """
    Test git integration for HEAD commit detection.
    """

    def test_git_not_available(self, tmp_path: Path):
        """
        When git is not available or fails, _detect_git_head returns None.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Even if we can't really uninstall git, we can mock run to fail
        from tools.rag_nav.gateway import _detect_git_head

        with patch("subprocess.run", side_effect=Exception("git not found")):
            head = _detect_git_head(repo_root)
            assert head is None

    def test_not_a_git_repo(self, tmp_path: Path):
        """
        When the path is not a git repository:
        - _detect_git_head returns None
        """
        repo_root = tmp_path / "not_git"
        repo_root.mkdir()

        from tools.rag_nav.gateway import _detect_git_head

        # Actual run without mock, assuming tmp_path is not a git repo
        head = _detect_git_head(repo_root)
        assert head is None

    def test_detached_head_state(self, tmp_path: Path):
        """
        When git is in detached HEAD state:
        - Should still be able to get commit hash
        """
        # We can simulate this by mocking the output of git rev-parse HEAD
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        from tools.rag_nav.gateway import _detect_git_head

        with patch("tools.rag_nav.gateway.run") as mock_run:
            mock_run.return_value.stdout = "detached_hash\n"
            mock_run.return_value.returncode = 0
            head = _detect_git_head(repo_root)
            assert head == "detached_hash"
