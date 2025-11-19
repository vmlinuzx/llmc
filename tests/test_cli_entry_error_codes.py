from __future__ import annotations

import json
from pathlib import Path

from tools.rag_repo import cli_entry


def test_cli_error_code_for_bad_workspace(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    code = cli_entry.main(
        ["doctor-paths", "--repo", str(repo), "--workspace", "../escape", "--json"]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "ERROR:" in err

