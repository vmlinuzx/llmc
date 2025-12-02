"""
Unit tests for compute_route - the RAG freshness gateway.

Tests routing decisions based on index state and git HEAD matching.
"""

from pathlib import Path
import subprocess

import pytest

from tools.rag_nav.gateway import compute_route
from tools.rag_nav.metadata import save_status, status_path
from tools.rag_nav.models import IndexStatus


def _init_git_repo(repo_path: Path, commit_sha: str = "abc123def456") -> str:
    """Initialize a git repo and return the HEAD SHA."""
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=False, cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=False, cwd=repo_path, capture_output=True)
    (repo_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, capture_output=True, check=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=repo_path, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.mark.rag_freshness
class TestComputeRoute:
    """Test the context gateway routing decision logic."""

    def test_no_status_file(self, tmp_path: Path):
        """No status file -> UNKNOWN, don't use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "UNKNOWN"
        assert route.status is None

    def test_stale_index_state(self, tmp_path: Path):
        """Stale index -> STALE, don't use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        status = IndexStatus(
            repo=str(repo_root),
            index_state="stale",
            last_indexed_at="2025-11-15T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )
        save_status(repo_root, status)
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_error_index_state(self, tmp_path: Path):
        """Error index -> STALE, don't use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        status = IndexStatus(
            repo=str(repo_root),
            index_state="error",
            last_indexed_at="2025-11-16T12:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error="Database locked",
        )
        save_status(repo_root, status)
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_fresh_index_no_git(self, tmp_path: Path):
        """Fresh index but no git repo -> UNKNOWN (can't verify HEAD)."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        status = IndexStatus(
            repo=str(repo_root),
            index_state="fresh",
            last_indexed_at="2025-11-17T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )
        save_status(repo_root, status)
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "UNKNOWN"

    def test_fresh_index_head_match(self, tmp_path: Path):
        """Fresh index + matching HEAD -> FRESH, use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        # Init git and get actual HEAD
        head_sha = _init_git_repo(repo_root)
        
        status = IndexStatus(
            repo=str(repo_root),
            index_state="fresh",
            last_indexed_at="2025-11-17T10:00:00Z",
            last_indexed_commit=head_sha,  # Matches current HEAD
            schema_version="1.0",
        )
        save_status(repo_root, status)
        
        route = compute_route(repo_root)
        
        assert route.use_rag is True
        assert route.freshness_state == "FRESH"
        assert route.status is not None

    def test_fresh_index_head_mismatch(self, tmp_path: Path):
        """Fresh index + mismatched HEAD -> STALE, don't use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        # Init git
        _init_git_repo(repo_root)
        
        status = IndexStatus(
            repo=str(repo_root),
            index_state="fresh",
            last_indexed_at="2025-11-17T10:00:00Z",
            last_indexed_commit="old_commit_that_doesnt_match",
            schema_version="1.0",
        )
        save_status(repo_root, status)
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "STALE"

    def test_malformed_status_file(self, tmp_path: Path):
        """Malformed JSON -> UNKNOWN, don't use RAG."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        # Write invalid JSON directly
        path = status_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ invalid json }", encoding="utf-8")
        
        route = compute_route(repo_root)
        
        assert route.use_rag is False
        assert route.freshness_state == "UNKNOWN"

    def test_route_decision_fields(self, tmp_path: Path):
        """RouteDecision has all required fields."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        
        route = compute_route(repo_root)
        
        assert hasattr(route, "use_rag")
        assert hasattr(route, "freshness_state")
        assert hasattr(route, "status")
        assert isinstance(route.use_rag, bool)
        assert route.freshness_state in ("FRESH", "STALE", "UNKNOWN")
