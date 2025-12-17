from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.cli import export_bundle


def test_export_force_guard(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    export_dir = repo / ".llmc" / "workspace" / "exports"
    export_dir.mkdir(parents=True)
    (export_dir / "existing.txt").write_text("x")
    # Should fail without force
    with pytest.raises(RuntimeError):
        export_bundle(repo, None, "exports", force=False)
    # Should succeed with force
    result = export_bundle(repo, None, "exports", force=True)
    assert "export_dir" in result
