from __future__ import annotations

from pathlib import Path

from tools.rag_repo.doctor import doctor_paths


def test_doctor_paths_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    info = doctor_paths(repo, None, "exports")
    assert info["workspace_exists"]
    assert info["export_exists"]
    assert info["under_workspace"]
