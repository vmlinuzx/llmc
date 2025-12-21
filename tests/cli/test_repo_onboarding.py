import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from typer.testing import CliRunner

from llmc.main import app

runner = CliRunner()


def setup_test_repo(tmp_path: Path) -> Path:
    """Set up a dummy repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()  # Mock git repo
    return repo_path


def test_repo_register_with_validation_and_embedding_check(tmp_path: Path):
    """
    Test that `repo register` runs validation and embedding checks.
    """
    repo_path = setup_test_repo(tmp_path)

    # Mock Ollama API response - model available
    mock_ollama_response = {
        "models": [{"name": "nomic-embed-text:latest"}]
    }

    with patch(
        "urllib.request.urlopen"
    ) as mock_urlopen, patch(
        "llmc.commands.repo_validator.validate_repo"
    ) as mock_validate_repo:
        # Configure the mock for urlopen
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_ollama_response).encode(
            "utf-8"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        # Configure the mock for validate_repo
        mock_validation_result = MagicMock()
        mock_validation_result.passed = True
        mock_validation_result.checks = []
        mock_validate_repo.return_value = mock_validation_result

        result = runner.invoke(
            app, ["repo", "register", str(repo_path), "--no-index"]
        )

        assert result.exit_code == 0
        assert "🚀 Registering test-repo with LLMC" in result.stdout
        assert "🔍 Running post-registration checks..." in result.stdout
        assert "nomic-embed-text" not in result.stdout  # No warning
        mock_validate_repo.assert_called_once()


def test_repo_register_embedding_model_not_found(tmp_path: Path):
    """
    Test `repo register` when embedding model is not in Ollama.
    """
    repo_path = setup_test_repo(tmp_path)

    # Mock Ollama API response - model NOT available
    mock_ollama_response = {"models": [{"name": "another-model:latest"}]}

    with patch("urllib.request.urlopen") as mock_urlopen, patch(
        "llmc.commands.repo_validator.validate_repo"
    ) as mock_validate_repo:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_ollama_response).encode(
            "utf-8"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        mock_validation_result = MagicMock()
        mock_validation_result.passed = True
        mock_validation_result.checks = []
        mock_validate_repo.return_value = mock_validation_result
        
        result = runner.invoke(
            app, ["repo", "register", str(repo_path), "--no-index"]
        )

        assert result.exit_code == 0
        assert "Warning: Embedding model 'nomic-embed-text' not found in Ollama" in result.stdout


def test_repo_register_ollama_not_running(tmp_path: Path):
    """
    Test `repo register` when Ollama is not reachable.
    """
    repo_path = setup_test_repo(tmp_path)

    with patch("urllib.request.urlopen") as mock_urlopen, patch(
        "llmc.commands.repo_validator.validate_repo"
    ) as mock_validate_repo:
        mock_urlopen.side_effect = URLError("Connection refused")
        
        mock_validation_result = MagicMock()
        mock_validation_result.passed = True
        mock_validation_result.checks = []
        mock_validate_repo.return_value = mock_validation_result

        result = runner.invoke(
            app, ["repo", "register", str(repo_path), "--no-index"]
        )

        assert result.exit_code == 0
        assert (
            "Warning: Ollama is not running or not reachable" in result.stdout
        )
