from pathlib import Path

import pytest

from llmc.docgen.gating import resolve_doc_path


def test_resolve_doc_path_absolute_input_ux_bug(tmp_path):
    """
    Demonstrate that passing an absolute path to a file INSIDE the repo
    currently fails validation because it treats it as an absolute override
    rather than converting to relative.
    """
    repo_root = tmp_path
    output_dir = "DOCS/REPODOCS"
    (repo_root / output_dir).mkdir(parents=True)

    # File inside the repo
    source_file = repo_root / "tools/rag/search.py"
    source_file.parent.mkdir(parents=True)
    source_file.touch()

    # User passes absolute path
    input_path = source_file.resolve()

    # Current implementation behavior:
    # It does: output_base / input_path
    # If input_path is absolute, result is input_path + ".md"
    # Then checks if that is inside output_base.
    # /tmp/repo/tools/rag/search.py.md is NOT inside /tmp/repo/DOCS/REPODOCS

    # So this SHOULD fail with ValueError currently.
    # This test confirms the "bug" exists.
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, input_path, output_dir=output_dir)


def test_resolve_doc_path_relative_input_works(tmp_path):
    """Confirm relative path works."""
    repo_root = tmp_path
    output_dir = "DOCS/REPODOCS"
    (repo_root / output_dir).mkdir(parents=True)

    input_path = Path("tools/rag/search.py")

    resolved = resolve_doc_path(repo_root, input_path, output_dir=output_dir)
    expected = (repo_root / output_dir / "tools/rag/search.py.md").resolve()

    assert resolved == expected
