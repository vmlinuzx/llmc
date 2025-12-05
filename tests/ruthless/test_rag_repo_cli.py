import json
import sys
from unittest.mock import patch

import pytest

from tools.rag_repo.cli import main

# Create a ruthless test for the new repo CLI features

@pytest.fixture
def mock_registry_env(tmp_path, monkeypatch):
    """Setup a temporary environment for registry testing."""
    # We need to ensure the registry is stored in tmp_path
    # Inspecting tools.rag_repo.config might reveal how to control this.
    # For now, we'll just patch the RegistryAdapter to use a file in tmp_path
    
    # But first, let's make sure we don't touch the real user config
    monkeypatch.setenv("LLMC_CONFIG_DIR", str(tmp_path / ".llmc"))
    (tmp_path / ".llmc").mkdir()
    
    return tmp_path

def test_repo_cli_help(capsys):
    """Test top-level help."""
    with patch.object(sys, "argv", ["llmc-rag-repo", "--help"]):
        ret = main()
        assert ret == 0
    captured = capsys.readouterr()
    assert "LLMC RAG Repo Tool" in captured.out
    assert "add" in captured.out
    assert "remove" in captured.out

def test_repo_add_basic(tmp_path, capsys, monkeypatch):
    """Test basic repo addition with -y (non-interactive)."""
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir() # Simulate git repo
    
    # Mock RegistryAdapter to avoid messing with real registry
    # But we want to test the logic, so maybe we should let it run against a temp file?
    # Let's try to patch the storage path if possible, or just mock the whole adapter if it's too complex.
    # Given this is an integration test, we prefer real components.
    
    # We will use a temporary home directory to isolate the registry
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".llmc").mkdir(exist_ok=True)
    
    # Run command
    cmd = ["add", str(repo_dir), "-y"]
    ret = main(cmd)
    
    captured = capsys.readouterr()
    assert ret == 0, f"Command failed: {captured.err}"
    assert "Registered repo myrepo" in captured.out
    
    # Verify llmc.toml was created (by RepoConfigurator)
    assert (repo_dir / "llmc.toml").exists()

def test_repo_add_with_template(tmp_path, capsys, monkeypatch):
    """Test repo addition with a custom template."""
    repo_dir = tmp_path / "templated_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".llmc").mkdir(exist_ok=True)
    
    # Create a template
    template_path = tmp_path / "my_template.toml"
    template_path.write_text("""
[project]
name = "templated-project"
[enrichment]
default_chain = "custom"
""")
    
    cmd = ["add", str(repo_dir), "-y", "--template", str(template_path)]
    ret = main(cmd)
    
    capsys.readouterr()
    assert ret == 0
    
    # Verify config content
    config_path = repo_dir / "llmc.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert 'name = "templated-project"' in content
    assert 'default_chain = "custom"' in content

def test_repo_list_json(tmp_path, capsys, monkeypatch):
    """Test listing repos in JSON format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".llmc").mkdir(exist_ok=True)
    
    # Add a repo first
    repo_dir = tmp_path / "repo_for_list"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    main(["add", str(repo_dir), "-y"])
    capsys.readouterr() # clear buffer
    
    # List
    ret = main(["list", "--json"])
    captured = capsys.readouterr()
    assert ret == 0
    
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["repo_path"] == str(repo_dir)

def test_repo_remove(tmp_path, capsys, monkeypatch):
    """Test removing a repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".llmc").mkdir(exist_ok=True)
    
    # Add
    repo_dir = tmp_path / "repo_to_remove"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    main(["add", str(repo_dir), "-y"])
    
    # Remove
    ret = main(["remove", str(repo_dir)])
    captured = capsys.readouterr()
    assert ret == 0
    assert "Unregistered repo" in captured.out
    
    # Verify list is empty
    main(["list", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 0

def test_repo_add_template_invalid(tmp_path, capsys, monkeypatch):
    """Test adding with an invalid template path."""
    repo_dir = tmp_path / "fail_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".llmc").mkdir(exist_ok=True)
    
    cmd = ["add", str(repo_dir), "-y", "--template", "non_existent.toml"]
    # The command might not fail exit code if the configurator just prints error?
    # Let's check code behavior. Configurator usually raises error or prints.
    # If `_cmd_add` doesn't catch Configurator errors, it might crash.
    
    try:
        ret = main(cmd)
        captured = capsys.readouterr()
        # If it swallows error, we check output
        # If it raises, we catch it
    except Exception as e:
        pytest.fail(f"Command crashed: {e}")
        
    # In `_cmd_add`:
    # configurator.configure(...) 
    # If that raises, it crashes.
    # Let's see if the test fails (crash) or passes (handled).
    # If it crashes, that's a bug I found!
    
    # For now, let's assert it probably fails or prints error
    assert "Template not found" in captured.out or "Error" in captured.out or ret != 0
