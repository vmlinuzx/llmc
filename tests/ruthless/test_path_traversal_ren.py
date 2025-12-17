from pathlib import Path

import pytest

from llmc.docgen.gating import resolve_doc_path


def test_resolve_doc_path_traversal_dotdot(tmp_path):
    """Test that ../ components are resolved and caught."""
    repo_root = tmp_path
    (repo_root / "DOCS/REPODOCS").mkdir(parents=True)

    # Attempt to break out
    relative_path = Path("../../outside.py")

    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, relative_path)


def test_resolve_doc_path_absolute_injection(tmp_path):
    """Test that absolute path injection is caught."""
    repo_root = tmp_path
    (repo_root / "DOCS/REPODOCS").mkdir(parents=True)

    # Absolute path (linux style)
    relative_path = Path("/etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, relative_path)


def test_resolve_doc_path_valid_nested(tmp_path):
    """Test that valid nested paths work."""
    repo_root = tmp_path
    (repo_root / "DOCS/REPODOCS").mkdir(parents=True)

    relative_path = Path("deeply/nested/file.py")
    resolved = resolve_doc_path(repo_root, relative_path)

    expected = (repo_root / "DOCS/REPODOCS/deeply/nested/file.py.md").resolve()
    assert resolved == expected


def test_resolve_doc_path_symlink_resolution(tmp_path):
    """Test that symlinks in the output path are resolved, but must still be inside base?
    Wait, resolve() resolves symlinks.
    If DOCS/REPODOCS is a symlink to /tmp, then output_base resolves to /tmp.
    And doc_path resolves to /tmp/file.md.
    So relative_to works.

    But if we inject a symlink in the filename?
    e.g. relative_path = "link_to_outside/file.py" where link_to_outside -> /etc
    """
    repo_root = tmp_path
    docs_dir = repo_root / "DOCS/REPODOCS"
    docs_dir.mkdir(parents=True)

    # Create a symlink inside DOCS/REPODOCS that points outside
    # Wait, we are constructing the path from relative_path.
    # The file doesn't have to exist to be resolved.
    # But if components of the path exist and are symlinks, resolve() follows them.

    # Scenario:
    # DOCS/REPODOCS/bad_link -> /etc
    # relative_path = "bad_link/passwd"
    # output_base = .../DOCS/REPODOCS
    # doc_path_candidate = .../DOCS/REPODOCS/bad_link/passwd.md
    # doc_path_resolved = /etc/passwd.md (if /etc/passwd.md existed?)
    # Actually resolve(strict=False) (default in 3.10+) resolves what it can.

    # Let's simulate this directory structure
    bad_link = docs_dir / "bad_link"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    bad_link.symlink_to(target_dir)

    # Now try to write to bad_link/file.py
    # relative_path = "bad_link/file.py"
    # resolved = .../target/file.py.md
    # output_base = .../DOCS/REPODOCS
    # resolved.relative_to(output_base) -> FAILS because target is outside REPODOCS

    relative_path = Path("bad_link/file.py")

    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, relative_path)
