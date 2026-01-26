from pathlib import Path

import pytest

from llmc_mcp.tools.rag import validate_repo_root


def test_repo_root_in_allowed_roots(tmp_path, monkeypatch):
    """Test valid repo_root passes validation."""
    allowed = str(tmp_path)

    monkeypatch.setattr("llmc_mcp.tools.rag.get_llmc_config", lambda: {"allowed_roots": [allowed]})

    result = validate_repo_root(str(tmp_path / "myrepo"))
    assert result == Path(tmp_path / "myrepo").resolve()

def test_repo_root_outside_allowed_roots(tmp_path, monkeypatch):
    """Test repo_root outside allowed_roots raises error."""
    allowed = str(tmp_path / "allowed")

    monkeypatch.setattr("llmc_mcp.tools.rag.get_llmc_config", lambda: {"allowed_roots": [allowed]})

    with pytest.raises(PermissionError, match="not under allowed_roots"):
        validate_repo_root("/etc/passwd")

def test_repo_root_no_allowed_roots_configured(monkeypatch):
    """Test backwards compatibility when no allowed_roots configured."""
    monkeypatch.setattr("llmc_mcp.tools.rag.get_llmc_config", lambda: {})
    # Should not raise
    result = validate_repo_root("/any/path")
    assert result == Path("/any/path").resolve()

def test_no_chdir_in_rag_tools():
    """Ensure os.chdir is not used in RAG tools."""
    import ast
    from pathlib import Path

    # Construct path relative to this test file to ensure it's found
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent.parent
    rag_file = repo_root / "llmc_mcp/tools/rag.py"

    assert rag_file.exists(), f"Could not find rag.py at {rag_file}"

    tree = ast.parse(rag_file.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "chdir":
                    pytest.fail("os.chdir() found in rag.py - should use explicit paths")
