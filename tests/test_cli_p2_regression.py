from pathlib import Path
from typer.testing import CliRunner
from llmc.cli import make_layout
from llmc.main import app

runner = CliRunner()

def test_cli_make_layout_deduplication():
    """Verify that make_layout is defined and valid."""
    assert callable(make_layout)

def test_init_command_b008_fix_execution():
    """Test that init command runs correctly after B008 fix."""
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Initializing LLMC workspace" in result.stdout
        assert (Path(".") / ".llmc").exists()
        assert (Path(".") / "llmc.toml").exists()

def test_init_command_with_explicit_path():
    """Test that init command runs correctly with explicit path."""
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init", "."])
        assert result.exit_code == 0
        assert "Initializing LLMC workspace" in result.stdout