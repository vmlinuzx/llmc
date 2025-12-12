import pytest
import json
import tempfile
from pathlib import Path

# Assuming SessionManager is located at llmc_agent/session.py
# If this import fails, I will need to adjust the path.
from llmc_agent.session import SessionManager, Session

@pytest.fixture
def temp_session_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        sessions_dir = root_path / "sessions"
        sessions_dir.mkdir()

        # Create a dummy session file outside the sessions directory
        outside_session_data = {
            "id": "outside_session",
            "created_at": "2025-12-12T11:00:00Z", # Added
            "updated_at": "2025-12-12T12:00:00Z", # Changed from last_active
            "model": "mock-model", # Changed from llm_config
            "repo_path": None, # Added
            "messages": [{"role": "user", "content": "Hello from outside!", "tokens": 5, "timestamp": "2025-12-12T12:00:00Z"}],
            "metadata": {}, # Added
        }
        outside_session_path = root_path / "outside.json"
        with open(outside_session_path, "w") as f:
            json.dump(outside_session_data, f)

        yield root_path, sessions_dir, outside_session_data

def test_session_path_traversal(temp_session_env):
    root_path, sessions_dir, expected_session_data = temp_session_env

    session_manager = SessionManager(storage_path=root_path)

    # Attempt to load a session using path traversal
    # The session_id ".." means we go up one directory from 'sessions_dir' (which is 'root_path'),
    # then look for 'outside.json'.
    traversal_session_id = "../outside"
    loaded_session = session_manager.load(traversal_session_id)

    assert loaded_session is not None, "Expected session to be loaded, but it was None."
    assert loaded_session.id == expected_session_data["id"], \
        "Loaded session ID does not match expected."
    assert loaded_session.messages[0].content == expected_session_data["messages"][0]["content"], \
        "Loaded session content does not match expected."

    # Further assert that the path used resolves outside the intended sessions_dir
    # This check is conceptual for validating the traversal itself,
    # as the 'load' method itself might not expose the resolved path directly.
    # However, the successful load with the correct content implicitly confirms the traversal.
    expected_full_path = root_path / "outside.json"
    actual_path_attempted = sessions_dir / f"{traversal_session_id}.json"
    assert actual_path_attempted.resolve() == expected_full_path.resolve(), \
        "The resolved path did not match the expected path for traversal."
