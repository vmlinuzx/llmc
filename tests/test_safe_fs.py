from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.fs import SafeFS
from llmc.rag_repo.utils import PathTraversalError


def test_safefs_write_read_list_rm(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    fs = SafeFS(base)

    # write
    with fs.open_write("a/b/c.txt") as handle:
        handle.write(b"hi")
    assert (base / "a" / "b" / "c.txt").exists()

    # read
    with fs.open_read("a/b/c.txt") as handle:
        assert handle.read() == b"hi"

    # list
    entries = fs.list_dir("a/b")
    assert any(path.name == "c.txt" for path in entries)

    # mkdir
    fs.mkdir_p("x/y/z")
    assert (base / "x" / "y" / "z").is_dir()

    # rm subtree
    fs.rm_tree("a")
    assert not (base / "a").exists()


def test_safefs_blocks_escape(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    fs = SafeFS(base)
    with pytest.raises(PathTraversalError):
        fs.open_write("../../etc/passwd")
