from __future__ import annotations

from pathlib import Path

from tools.rag_repo.tmpfs import SafeTmp


def test_safetmp_make_and_cleanup(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    ws = repo / ".llmc" / "workspace"
    ws.mkdir(parents=True)
    st = SafeTmp(ws)
    path = st.make("unittest")
    assert path.is_dir()
    st.cleanup(path)
    assert not path.exists()


def test_safetmp_base_scoped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    ws = repo / ".llmc" / "workspace"
    ws.mkdir(parents=True)
    st = SafeTmp(ws)
    base = st.base()
    assert str(base).startswith(str(ws))
