from typer.testing import CliRunner
from llmc.mcinspect import app
from pathlib import Path

runner = CliRunner()


def test_mcinspect_symbol_not_found():
    with runner.isolated_filesystem():
        Path(".git").mkdir()
        result = runner.invoke(app, ["lookup", "non_existent_symbol"])
        assert result.exit_code != 0
        assert "Symbol not found" in result.stdout


def test_mcinspect_raw():
    with runner.isolated_filesystem():
        Path(".git").mkdir()
        result = runner.invoke(app, ["lookup", "--raw", "main"])
        assert result.exit_code == 0
        assert "Graph Neighbors" not in result.stdout
        assert "def main" in result.stdout


def test_mcinspect_json():
    with runner.isolated_filesystem():
        Path(".git").mkdir()
        result = runner.invoke(app, ["lookup", "--json", "main"])
        assert result.exit_code == 0
        assert '"symbol": "main"' in result.stdout
        assert '"graph_context":' in result.stdout


def test_mcinspect_with_graph_context():
    with runner.isolated_filesystem():
        Path(".git").mkdir()
        result = runner.invoke(app, ["lookup", "main"])
        assert result.exit_code == 0
        assert "Graph Neighbors" in result.stdout
        assert "def main" in result.stdout
