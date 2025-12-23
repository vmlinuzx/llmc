from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmc.cli import DashboardState, get_repo_stats


@pytest.fixture
def mock_repo_root(tmp_path):
    return tmp_path

def test_get_repo_stats_load_graph_unexpected_data(mock_repo_root):
    """
    Test that get_repo_stats handles the case where _load_graph returns
    an unexpected data structure (e.g., not a tuple).
    """
    with patch("llmc.cli._load_graph") as mock_load_graph:
        # _load_graph is expected to return (nodes, edges)
        # We mock it to return just a list, which should cause a ValueError during unpacking
        mock_load_graph.return_value = ["invalid_data"]
        
        # Also mock load_status to avoid issues there
        with patch("llmc.cli.load_status") as mock_load_status:
            mock_load_status.return_value = None
            
            stats = get_repo_stats(mock_repo_root)
            
            assert stats["error"] is not None
            # The exact error message depends on python version ("too many values to unpack" or similar)
            # but we just check that an error was caught.
            assert stats["freshness_state"] == "ERROR"
            assert stats["daemon_status"] == "ERROR"

def test_get_repo_stats_load_status_exception(mock_repo_root):
    """
    Test that get_repo_stats handles an exception raised by load_status.
    """
    with patch("llmc.cli.load_status") as mock_load_status:
        error_msg = "Failed to load status"
        mock_load_status.side_effect = RuntimeError(error_msg)
        
        stats = get_repo_stats(mock_repo_root)
        
        assert stats["error"] == error_msg
        assert stats["freshness_state"] == "ERROR"
        assert stats["daemon_status"] == "ERROR"

def test_get_repo_stats_load_graph_exception(mock_repo_root):
    """
    Test that get_repo_stats handles an exception raised by _load_graph.
    """
    with patch("llmc.cli._load_graph") as mock_load_graph:
        error_msg = "Graph loading failed"
        mock_load_graph.side_effect = ValueError(error_msg)
        
        # Mock load_status to pass
        with patch("llmc.cli.load_status") as mock_load_status:
            mock_load_status.return_value = None
            
            stats = get_repo_stats(mock_repo_root)
            
            assert stats["freshness_state"] == "ERROR"
            assert stats["daemon_status"] == "ERROR"


def test_get_repo_stats_success(mock_repo_root):
    """
    Test that get_repo_stats returns correct statistics when dependencies return valid data.
    """
    # Setup mock data for graph
    mock_nodes = [
        {"id": "node1", "metadata": {"summary": "This is a summary."}},  # 18 chars
        {"id": "node2", "metadata": {}},  # No summary
        {"id": "node3", "metadata": {"summary": "Short."}},  # 6 chars
    ]
    # Total summary length: 18 + 0 + 6 = 24. Token usage = 24 // 4 = 6.
    
    # Setup mock data for status
    mock_status = MagicMock()
    mock_status.index_state = "FRESH"
    mock_status.last_indexed_at = "2023-10-27T10:00:00"

    # Setup file for daemon status
    (mock_repo_root / ".llmc" / "rag").mkdir(parents=True, exist_ok=True)
    (mock_repo_root / ".llmc" / "rag" / "index_v2.db").touch()

    with patch("llmc.cli._load_graph", return_value=(mock_nodes, [])):
        with patch("llmc.cli.load_status", return_value=mock_status):
            
            stats = get_repo_stats(mock_repo_root)
            
            assert stats["error"] is None
            assert stats["graph_nodes"] == 3
            assert stats["enriched_nodes"] == 2
            assert stats["freshness_state"] == "FRESH"
            assert stats["last_indexed_at"] == "2023-10-27T10:00:00"
            assert stats["token_usage"] == 6
            assert stats["daemon_status"] == "ONLINE"
            assert stats["files_tracked"] == 3


from typer.testing import CliRunner

from llmc.cli import app

runner = CliRunner()

def test_route_valid_file_path():
    """Test that a valid file path returns the expected domain."""
    with patch("llmc.rag.routing.resolve_domain") as mock_resolve:
        mock_resolve.return_value = ("coding", "extension", "*.py")
        result = runner.invoke(app, ["route", "--test", "test.py"])
        assert result.exit_code == 0
        assert "Domain: coding" in result.stdout

def test_route_invalid_file_path():
    """Test that an error during resolution is handled gracefully."""
    with patch("llmc.rag.routing.resolve_domain") as mock_resolve:
        mock_resolve.side_effect = ValueError("Simulated error")
        result = runner.invoke(app, ["route", "--test", "error.py"])
        assert result.exit_code != 0
        assert "Error resolving domain" in result.stdout

@pytest.mark.parametrize(
    "path_input",
    [
        "../secret.txt",
        "foo/../../bar.txt",
        "/etc/passwd",
        "foo/bar/../../../etc/passwd",
    ],
)
def test_route_path_traversal_variations(path_input):
    """Test that various path traversal attempts are rejected."""
    result = runner.invoke(app, ["route", "--test", path_input])
    assert result.exit_code != 0
    assert "Security Error: Path traversal detected" in result.stdout

def test_dashboard_state_add_log():
    """Test that the DashboardState log management works correctly."""
    state = DashboardState(Path("."))
    
    # Test adding a single log
    state.add_log("test message", "INF")
    assert len(state.logs) == 1
    assert "test message" in state.logs[0]
    
    # Test log rotation
    for i in range(20):
        state.add_log(f"message {i}", "OK ")
    
    assert len(state.logs) == 15
    assert "message 5" in state.logs[0] # Should be the first of the last 15
    assert "message 19" in state.logs[-1]

@patch('llmc.cli.get_repo_stats')
def test_dashboard_state_update_success(mock_get_repo_stats, mock_repo_root):
    """Test the update method on success."""
    mock_get_repo_stats.return_value = {"files_tracked": 10, "error": None}
    state = DashboardState(mock_repo_root)
    state.update()
    
    mock_get_repo_stats.assert_called_once_with(mock_repo_root)
    assert state.current_stats["files_tracked"] == 10
    assert any("Stats refreshed" in log for log in state.logs)

@patch('llmc.cli.get_repo_stats')
def test_dashboard_state_update_error(mock_get_repo_stats, mock_repo_root):
    """Test the update method on error."""
    mock_get_repo_stats.return_value = {"error": "a big error"}
    state = DashboardState(mock_repo_root)
    state.update()

    mock_get_repo_stats.assert_called_once_with(mock_repo_root)
    assert "a big error" in state.current_stats["error"]
    assert any("Error fetching stats" in log for log in state.logs)
    assert any("a big error" in log for log in state.logs)

def test_search_command():
    """Test that the demo search command runs without error."""
    result = runner.invoke(app, ["search", "test query"])
    assert result.exit_code == 0
    assert "Searching for test query..." in result.stdout