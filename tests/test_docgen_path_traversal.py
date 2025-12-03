
import pytest
from pathlib import Path
from llmc.docgen.gating import resolve_doc_path

def test_resolve_doc_path_traversal(tmp_path):
    """Test that resolve_doc_path allows path traversal (Security Gap)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Target outside the intended output directory
    # Intended: repo/DOCS/REPODOCS/...
    # Attack: repo/target.md
    
    relative_path = Path("../../target")
    
    doc_path = resolve_doc_path(repo_root, relative_path, output_dir="DOCS/REPODOCS")
    
    # Verify it resolved to where we expect (outside REPODOCS)
    expected_path = repo_root / "target.md"
    
    # Note: resolve() is needed to normalize paths to compare, but doc_path might not exist yet.
    # We can check string representation or parents.
    
    # resolve_doc_path does: repo_root / output_dir / f"{relative_path}.md"
    # which is: repo/DOCS/REPODOCS/../../target.md
    # which collapses to: repo/target.md
    
    assert doc_path.resolve() == expected_path.resolve()
    
    # Even worse: completely outside repo
    relative_path_outside = Path("../../../outside")
    doc_path_outside = resolve_doc_path(repo_root, relative_path_outside, output_dir="DOCS/REPODOCS")
    
    expected_outside = tmp_path / "outside.md"
    assert doc_path_outside.resolve() == expected_outside.resolve()

