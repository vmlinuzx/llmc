from __future__ import annotations

import os

import pytest

from llmc.rag_repo.fs import SafeFS
from llmc.rag_repo.utils import PathTraversalError


@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="symlink not supported on this platform"
)
def test_symlink_escape_blocked(tmp_path) -> None:
    base = tmp_path / "root"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    # link inside base -> outside
    link = base / "link"
    os.symlink(outside, link, target_is_directory=True)
    (outside / "file.txt").write_text("x")
    fs = SafeFS(base)
    with pytest.raises(PathTraversalError):
        # attempt to read via symlinked path should resolve outside and be blocked
        fs.open_read("link/file.txt")
