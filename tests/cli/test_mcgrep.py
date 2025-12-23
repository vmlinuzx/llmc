from pathlib import Path
import sys
from unittest import mock

import pytest
from typer.testing import CliRunner

from llmc.mcgrep import (
    _format_source_indicator,
    _merge_line_ranges,
    _normalize_result_path,
    app,
    main,
)
from llmc.training_data import ToolCallExample

runner = CliRunner()


# --- Unit Tests for Helper Functions ---

def test_format_source_indicator():
    assert "semantic" in _format_source_indicator("RAG_GRAPH", "FRESH")
    assert "stale" in _format_source_indicator("RAG_GRAPH", "STALE")
    assert "fallback" in _format_source_indicator("OTHER", "FRESH")


def test_normalize_result_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Relative path inside repo
    assert _normalize_result_path(repo_root, Path("src/main.py")) == Path("src/main.py")
    
    # Absolute path inside repo
    abs_path = repo_root / "src/main.py"
    assert _normalize_result_path(repo_root, abs_path) == Path("src/main.py")
    
    # Absolute path outside repo
    outside_path = tmp_path / "other/file.py"
    assert _normalize_result_path(repo_root, outside_path) is None
    
    # String input
    assert _normalize_result_path(repo_root, "src/main.py") == Path("src/main.py")
    
    # Invalid input - effectively becomes "123"
    assert _normalize_result_path(repo_root, 123) == Path("123")


def test_merge_line_ranges():
    # Empty
    assert _merge_line_ranges([]) == []
    
    # Single
    assert _merge_line_ranges([(1, 10)]) == [(1, 10)]
    
    # Disjoint
    assert _merge_line_ranges([(1, 5), (10, 15)]) == [(1, 5), (10, 15)]
    
    # Overlapping
    assert _merge_line_ranges([(1, 10), (5, 15)]) == [(1, 15)]
    
    # Adjacent
    assert _merge_line_ranges([(1, 10), (11, 20)]) == [(1, 20)]
    
    # Contained
    assert _merge_line_ranges([(1, 20), (5, 10)]) == [(1, 20)]
    
    # Unsorted input
    assert _merge_line_ranges([(10, 15), (1, 5)]) == [(1, 5), (10, 15)]


# --- Integration Tests (CLI Logic) ---

def test_main_no_args():
    """Test that running mcgrep without args prints custom help."""
    with (
        mock.patch("sys.argv", ["mcgrep"]),
        mock.patch("llmc.mcgrep.console.print") as mock_print
    ):
        main()
        # Verify some help text was printed
        assert mock_print.call_count > 0
        assert "mcgrep" in str(mock_print.call_args_list[0])


def test_main_bare_query_insertion():
    """Test that a bare query injects the 'search' command."""
    with (
        mock.patch("sys.argv", ["mcgrep", "query"]),
        mock.patch("llmc.mcgrep.app") as mock_app
    ):
        main()
        assert sys.argv == ["mcgrep", "search", "query"]
        mock_app.assert_called_once()


def test_main_known_command_passthrough():
    """Test that known commands are passed through untouched."""
    with (
        mock.patch("sys.argv", ["mcgrep", "status"]),
        mock.patch("llmc.mcgrep.app") as mock_app
    ):
        main()
        assert sys.argv == ["mcgrep", "status"]
        mock_app.assert_called_once()


# --- Integration Tests (Search Command) ---

@pytest.fixture
def mock_search_env():
    with (
        mock.patch("llmc.mcgrep.find_repo_root") as mock_root,
        mock.patch("llmc.rag.search.search_spans") as mock_search,
        mock.patch("llmc.rag.config.index_path_for_read"),
        mock.patch("llmc.rag.database.Database"),
    ):
        mock_root.return_value = Path("/mock/repo")
        
        # Setup basic search result item
        mock_item = mock.Mock()
        mock_item.path = Path("src/test.py")
        mock_item.start_line = 10
        mock_item.end_line = 20
        mock_item.normalized_score = 95.0
        mock_item.summary = "Test summary"
        mock_item.symbol = "test_func"
        
        mock_search.return_value = [mock_item]
        
        yield mock_search


def test_search_basic(mock_search_env):
    result = runner.invoke(app, ["search", "query"])
    assert result.exit_code == 0
    assert "src/test.py" in result.stdout
    assert "L10-20" in result.stdout
    assert "Test summary" in result.stdout


def test_search_mutually_exclusive():
    result = runner.invoke(app, ["search", "query", "--extract", "1", "--expand", "1"])
    assert result.exit_code != 0
    # Typer/Click puts BadParameter messages in stderr or output
    assert "not both" in (result.stdout + str(result.stderr))


def test_search_no_repo():
    with mock.patch(
        "llmc.mcgrep.find_repo_root", side_effect=Exception("No repo")
    ):
        result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 1
        assert "Not in an LLMC-indexed repository" in result.stdout


def test_search_emit_training(mock_search_env):
    with mock.patch("llmc.mcgrep.emit_training_example") as mock_emit:
        mock_emit.return_value = '{"json": "output"}'
        result = runner.invoke(app, ["search", "query", "--emit-training"])
        assert result.exit_code == 0
        mock_emit.assert_called_once()
        # Verify the Example object passed to emit
        args = mock_emit.call_args[0][0]
        assert isinstance(args, ToolCallExample)
        assert args.tool_name == "rag_search"
        assert args.arguments["query"] == "query"


def test_search_expanded():
    """Test the --expand (LLM mode) flow."""
    with (
        mock.patch("llmc.mcgrep.find_repo_root") as mock_root,
        mock.patch("llmc.rag_nav.tool_handlers.tool_rag_search") as mock_tool_search,
        mock.patch("pathlib.Path.read_text", return_value="line1\nline2\nline3"),
    ):
        mock_root.return_value = Path("/mock/repo")

        # Mock tool result
        mock_item = mock.Mock()
        mock_item.snippet.location.path = Path("src/test.py")
        mock_item.snippet.location.start_line = 1
        mock_item.snippet.location.end_line = 2
        mock_item.file = "src/test.py"

        mock_result = mock.Mock()
        mock_result.items = [mock_item]
        mock_tool_search.return_value = mock_result

        result = runner.invoke(app, ["search", "query", "--expand", "1"])
        assert result.exit_code == 0
        assert "Returning full content" in result.stdout
        assert "src/test.py" in result.stdout
        # read_text is mocked, so we should see the content
        assert "line1" in result.stdout


def test_search_extracted(mock_search_env):
    """Test the --extract (thin mode) flow."""
    with mock.patch("pathlib.Path.read_text", return_value="line1\nline2\nline3"):
        result = runner.invoke(app, ["search", "query", "--extract", "1"])
        assert result.exit_code == 0
        assert "Mode: extract" in result.stdout
        assert "src/test.py" in result.stdout
        # Should show context
        assert "line1" in result.stdout


# --- Integration Tests (Other Commands) ---


def test_watch_command():
    with mock.patch("llmc.commands.service.start") as mock_start:
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert "Starting mcgrep watcher" in result.stdout
        mock_start.assert_called_once()


def test_status_command():
    with (
        mock.patch("llmc.mcgrep.find_repo_root") as mock_root,
        mock.patch("llmc.rag.doctor.run_rag_doctor") as mock_doc,
    ):
        mock_root.return_value = Path("/mock/repo")
        mock_doc.return_value = {
            "status": "OK",
            "files": 10,
            "spans": 100,
            "enriched": 100,
            "embedded": 100,
            "pending_enrichment": 0,
        }

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Index healthy" in result.stdout
        assert "Files: 10" in result.stdout


def test_init_command():
    with mock.patch("llmc.commands.repo.register") as mock_register:
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Registering repository" in result.stdout
        mock_register.assert_called_once_with(
            path=".", skip_index=False, skip_enrich=True
        )


def test_stop_command():
    with mock.patch("llmc.commands.service.stop") as mock_stop:
        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()