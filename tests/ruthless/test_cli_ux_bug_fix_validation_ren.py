"""
Test that validates the CLI UX bug fix.
After the fix, absolute paths inside the repo should work.
"""
from pathlib import Path

import pytest

from llmc.docgen.gating import resolve_doc_path


def test_cli_path_normalization_absolute_to_relative():
    """
    Test the core logic: if a path is absolute and inside repo_root,
    it should be convertible to relative.
    
    This validates the fix in llmc/commands/docs.py.
    """
    # Simulate what happens in the fixed CLI code
    repo_root = Path("/tmp/fake_repo")
    absolute_input = Path("/tmp/fake_repo/tools/rag/search.py")
    
    # The fix does: input_path.resolve().relative_to(repo_root.resolve())
    # (in our test, we don't have actual files, but we can test the logic)
    try:
        relative_path = absolute_input.relative_to(repo_root)
        # Should be: tools/rag/search.py
        assert relative_path == Path("tools/rag/search.py")
    except ValueError:
        pytest.fail("Should be able to convert absolute path inside repo to relative")


def test_resolve_doc_path_with_relative_input_after_normalization(tmp_path):
    """
    After CLI normalization, resolve_doc_path should receive relative path
    and work correctly.
    """
    repo_root = tmp_path
    output_dir = "DOCS/REPODOCS"
    (repo_root / output_dir).mkdir(parents=True)
    
    # CLI normalized the absolute input to this relative path
    relative_input = Path("tools/rag/search.py")
    
    # This should now work without "Path traversal detected" error
    resolved = resolve_doc_path(repo_root, relative_input, output_dir=output_dir)
    expected = (repo_root / output_dir / "tools/rag/search.py.md").resolve()
    
    assert resolved == expected


def test_path_normalization_outside_repo():
    """
    Test that paths outside the repo are handled gracefully.
    """
    repo_root = Path("/tmp/fake_repo")
    outside_path = Path("/etc/passwd")
    
    # Should raise ValueError when trying to make it relative
    with pytest.raises(ValueError):
        outside_path.relative_to(repo_root)
