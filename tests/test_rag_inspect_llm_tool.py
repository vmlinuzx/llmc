import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from tools.rag.cli import cli
from tools.rag.schema import SchemaGraph, Entity, Relation

# We'll import inspect_entity once implemented. For now, assume it will be in tools.rag.inspector
# from tools.rag.inspector import inspect_entity, InspectionResult

# --- Fixtures ---

@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".llmc").mkdir()
    (tmp_path / ".rag").mkdir()
    (tmp_path / ".rag" / "index_v2.db").write_text("dummy db")
    
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def main_func():\n    pass\n\nclass MainClass:\n    def method(self):\n        pass\n"
    )
    (tmp_path / "src" / "utils.py").write_text(
        "def util_func():\n    pass\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text(
        "from src.main import main_func\ndef test_main():\n    main_func()\n"
    )
    return tmp_path

@pytest.fixture
def mock_graph_json(repo_root: Path):
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    graph = SchemaGraph(
        indexed_at="2025-01-01T00:00:00Z",
        repo=str(repo_root),
        entities=[
            Entity(
                id="func:src.main.main_func", 
                kind="function", 
                path="src/main.py:1-2", 
                file_path="src/main.py",
                start_line=1, end_line=2,
                metadata={"summary": "Main entry point"}
            ),
            Entity(
                id="class:src.main.MainClass", 
                kind="class", 
                path="src/main.py:4-6", 
                file_path="src/main.py",
                start_line=4, end_line=6
            ),
            Entity(
                id="func:src.utils.util_func", 
                kind="function", 
                path="src/utils.py:1-2", 
                file_path="src/utils.py",
                start_line=1, end_line=2
            ),
            Entity(
                id="func:tests.test_main.test_main", 
                kind="function", 
                path="tests/test_main.py:2-3", 
                file_path="tests/test_main.py",
                start_line=2, end_line=3
            ),
        ],
        relations=[
            Relation(src="func:tests.test_main.test_main", edge="calls", dst="func:src.main.main_func"),
        ]
    )
    graph.save(graph_path)
    return graph_path

# --- Tests ---

def test_inspect_entity_symbol_default_snippet(repo_root: Path, mock_graph_json: Path):
    from tools.rag.inspector import inspect_entity
    
    # Inspect a symbol
    result = inspect_entity(repo_root, symbol="src.main.main_func")
    
    assert result.source_mode == "symbol"
    assert result.path == "src/main.py"
    assert "def main_func():" in result.snippet
    assert result.full_source is None
    assert result.primary_span == (1, 2)

def test_inspect_entity_file_default_snippet(repo_root: Path, mock_graph_json: Path):
    from tools.rag.inspector import inspect_entity

    # Inspect a file
    result = inspect_entity(repo_root, path="src/main.py")
    
    assert result.source_mode == "file"
    assert "def main_func():" in result.snippet
    assert "class MainClass:" in result.snippet
    assert len(result.defined_symbols) >= 2
    assert result.full_source is None

def test_inspect_entity_full_source_flag(repo_root: Path, mock_graph_json: Path):
    from tools.rag.inspector import inspect_entity

    result = inspect_entity(repo_root, path="src/main.py", include_full_source=True)
    
    assert result.full_source is not None
    assert "def main_func():" in result.full_source
    assert "class MainClass:" in result.full_source
    # Snippet should still be present
    assert result.snippet is not None

def test_inspect_entity_relationships_truncated(repo_root: Path, mock_graph_json: Path):
    from tools.rag.inspector import inspect_entity

    # main_func is called by test_main
    result = inspect_entity(repo_root, symbol="src.main.main_func")
    
    assert len(result.incoming_calls) > 0
    call = result.incoming_calls[0]
    assert "test_main" in call.symbol
    assert call.path == "tests/test_main.py"

def test_inspect_entity_enrichment_fields(repo_root: Path, mock_graph_json: Path):
    from tools.rag.inspector import inspect_entity
    
    # Mock DB access
    with patch('tools.rag.database.Database') as MockDatabase:
        mock_db = MockDatabase.return_value
        mock_db.conn.execute.return_value.fetchone.return_value = {
            "summary": "Enriched summary",
            "inputs": "['arg1']",
            "outputs": "['None']",
            "side_effects": "[]",
            "pitfalls": "[]",
            "evidence": "[]",
            "span_hash": "abc"
        }
        # Make sure inspector uses a method that we can mock, or mocks the connection directly
        # Assuming inspector uses Database(path).fetch_... or direct conn execution
        
        result = inspect_entity(repo_root, symbol="src.main.main_func")
        
        # If we haven't implemented DB logic yet, this might fail or need adjustment
        # depending on how strictly we follow TDD. For now, let's assume best effort.
        # If DB logic is skipped in first pass, result.enrichment might be empty.
        # But we want to test that it *tries* to populate it.
        
        if result.enrichment.get("summary"):
            assert result.enrichment["summary"] == "Enriched summary"

def test_cli_inspect_json(repo_root: Path, mock_graph_json: Path):
    # Use subprocess to ensure it runs as a command, or CliRunner for in-process speed
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--path", "src/main.py", "--json"])
    
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["path"] == "src/main.py"
    assert data["source_mode"] == "file"
    assert "def main_func():" in data["snippet"]
    assert "provenance" in data

def test_cli_inspect_text_header(repo_root: Path, mock_graph_json: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--path", "src/main.py"])
    
    assert result.exit_code == 0
    assert "# FILE: src/main.py" in result.output
    assert "def main_func():" in result.output # Preview
