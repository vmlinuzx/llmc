# SDD: Missing Test Coverage for DashboardState Class

## 1. Gap Description
The `monitor` command in `llmc/cli.py` relies on the `DashboardState` class to manage its state. This class contains logic for adding and rotating log messages (`add_log`) and for refreshing repository statistics (`update`). Currently, there is no test coverage for this class, meaning we cannot be sure that the TUI is being driven by correct data.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
Unit tests should be added for the `DashboardState` class.

- **`test_dashboard_state_add_log`**: This test will check the `add_log` method. It should verify that a message is added to the `logs` list and that the list is correctly truncated when it exceeds the maximum size (15 entries).
- **`test_dashboard_state_update`**: This test will check the `update` method. It should be tested for two scenarios:
    1.  When `get_repo_stats` returns valid data: The test should patch `get_repo_stats`, assert that it was called, and that `state.current_stats` is updated.
    2.  When `get_repo_stats` returns an error: The test should patch `get_repo_stats` to return a dictionary with an 'error' key, and assert that an error message is added to the logs.

## 4. Implementation Details
The new tests should be added to `tests/cli/test_cli.py`.

```python
from llmc.cli import DashboardState

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

```
The necessary imports (`Path`) and the `mock_repo_root` fixture are already available in the file.
