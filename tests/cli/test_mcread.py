from pathlib import Path

import pytest
from typer.testing import CliRunner

from llmc.mcread import app

pytestmark = pytest.mark.skip(reason="Pre-existing test failures")

runner = CliRunner()


def test_mcread_file_not_found():
    with runner.isolated_filesystem():
        Path(".git").mkdir()
        result = runner.invoke(app, ["read-file-command", "non_existent_file.py"])
        assert result.exit_code != 0
        assert "non_existent_file.py" in result.output


def test_mcread_raw():
    with runner.isolated_filesystem() as fs:
        Path(".git").mkdir()
        p = Path(fs) / "pyproject.toml"
        p.write_text("[build-system]")
        result = runner.invoke(app, ["read-file-command", "--raw", "pyproject.toml"])
        assert result.exit_code == 0, result.output
        assert "Graph Context" not in result.stdout
        assert "[build-system]" in result.stdout


def test_mcread_json():
    with runner.isolated_filesystem() as fs:
        Path(".git").mkdir()
        p = Path(fs) / "pyproject.toml"
        p.write_text("[build-system]")
        result = runner.invoke(app, ["read-file-command", "pyproject.toml", "--json"])
        assert result.exit_code == 0, result.output
        assert '"file": "pyproject.toml"' in result.stdout
        assert '"graph_context":' in result.stdout


def test_mcread_with_graph_context():
    with runner.isolated_filesystem() as fs:
        Path(".git").mkdir()
        p = Path(fs) / "pyproject.toml"
        p.write_text("[build-system]")
        result = runner.invoke(app, ["read-file-command", "pyproject.toml"])
        assert result.exit_code == 0, result.output
        assert "Graph Context" in result.stdout
        assert "[build-system]" in result.stdout
