
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from llmc.commands.wizard import run_wizard, _check_ollama
import typer

def test_check_ollama_success():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "qwen2.5:3b"}, {"name": "nomic-embed-text"}]}

        connected, models = _check_ollama("http://localhost:11434")
        assert connected is True
        assert "qwen2.5:3b" in models
        assert "nomic-embed-text" in models

def test_check_ollama_failure():
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection error")

        connected, models = _check_ollama("http://localhost:11434")
        assert connected is False
        assert models == []

@patch("llmc.commands.wizard.Prompt.ask")
@patch("llmc.commands.wizard.Confirm.ask")
@patch("llmc.commands.wizard._check_ollama")
def test_run_wizard_flow(mock_check, mock_confirm, mock_prompt, tmp_path):
    # Setup mocks
    mock_check.return_value = (True, ["qwen2.5:3b", "nomic-embed-text"])

    # Prompt responses:
    # 1. Ollama URL (default)
    # 2. Tier 1 model
    # 3. Tier 2 model (skip) - returns None
    # 4. Embed model

    # Note: _select_model calls Prompt.ask.
    # If we return "skip" for Tier 2, _select_model returns None.

    mock_prompt.side_effect = [
        "http://localhost:11434", # URL
        "qwen2.5:3b",             # Tier 1
        "skip",                   # Tier 2
        "nomic-embed-text"        # Embed
    ]

    # Confirms:
    # Run validation? (False)
    mock_confirm.return_value = False

    # Run wizard with tmp_path
    run_wizard(repo_path=tmp_path)

    # Verify config generated
    config_path = tmp_path / "llmc.toml"
    assert config_path.exists()

    import tomli
    with open(config_path, "rb") as f:
        config = tomli.load(f)

    assert config["enrichment"]["chain"][0]["model"] == "qwen2.5:3b"
    assert len(config["enrichment"]["chain"]) == 1
    assert config["embeddings"]["profiles"]["docs"]["model"] == "nomic-embed-text"

@patch("llmc.commands.wizard.Prompt.ask")
@patch("llmc.commands.wizard.Confirm.ask")
@patch("llmc.commands.wizard._check_ollama")
def test_run_wizard_models_only(mock_check, mock_confirm, mock_prompt, tmp_path):
    # Create existing config
    import tomli_w
    config_path = tmp_path / "llmc.toml"
    initial_config = {
        "existing": "value",
        "enrichment": {"chain": [{"model": "old"}]},
        "embeddings": {"profiles": {"docs": {"model": "old"}}}
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(initial_config, f)

    # Setup mocks
    mock_check.return_value = (True, ["new-model", "new-embed"])

    mock_prompt.side_effect = [
        "http://localhost:11434", # URL
        "new-model",              # Tier 1
        "skip",                   # Tier 2
        "new-embed"               # Embed
    ]

    mock_confirm.return_value = False

    run_wizard(repo_path=tmp_path, models_only=True)

    import tomli
    with open(config_path, "rb") as f:
        config = tomli.load(f)

    assert config["existing"] == "value" # Preserved
    assert config["enrichment"]["chain"][0]["model"] == "new-model"
    assert config["embeddings"]["profiles"]["docs"]["model"] == "new-embed"
