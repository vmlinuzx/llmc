
import pytest
from pathlib import Path
from llmc.docgen.gating import resolve_doc_path

def test_resolve_doc_path_traversal_blocked(tmp_path):
    """Test that resolve_doc_path BLOCKS path traversal attacks (Security Fix)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Test 1: Attempt to traverse outside REPODOCS directory
    # Attack: repo/target.md (outside the intended DOCS/REPODOCS)
    relative_path = Path("../../target")
    
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, relative_path, output_dir="DOCS/REPODOCS")
    
    # Test 2: Attempt to traverse completely outside repo
    relative_path_outside = Path("../../../outside")
    
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, relative_path_outside, output_dir="DOCS/REPODOCS")
    
    # Test 3: Verify legitimate paths still work
    legitimate_path = Path("tools/rag/database.py")
    doc_path = resolve_doc_path(repo_root, legitimate_path, output_dir="DOCS/REPODOCS")
    
    # Should be: repo/DOCS/REPODOCS/tools/rag/database.py.md
    expected = repo_root / "DOCS" / "REPODOCS" / "tools" / "rag" / "database.py.md"
    assert doc_path == expected.resolve()

