from __future__ import annotations

from pathlib import Path
import tarfile

from llmc.rag_repo.archive import create_snapshot_tar
from llmc.rag_repo.fs import SafeFS


def test_snapshot_creates_tar(tmp_path: Path) -> None:
    base = tmp_path / "repo" / ".llmc" / "workspace"
    base.mkdir(parents=True)
    (base / "dir").mkdir()
    (base / "dir" / "f.txt").write_text("hi")
    fs = SafeFS(base)
    out = create_snapshot_tar(
        fs, ".", "exports/test-snap.tar.gz", include_hidden=False, force=True
    )
    assert out.exists()
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
        assert "dir/f.txt" in names
