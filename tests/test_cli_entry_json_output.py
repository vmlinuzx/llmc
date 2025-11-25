from __future__ import annotations

import json

from tools.rag_repo import cli_entry


def test_cli_json_output(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    code = cli_entry.main(["doctor-paths", "--repo", str(repo), "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "workspace_root" in data

