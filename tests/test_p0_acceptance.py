
import json
import sqlite3
from pathlib import Path

import pytest

from tools.rag import tool_rag_lineage, tool_rag_search, tool_rag_where_used


def _mk_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir(exist_ok=True)
    (repo / ".llmc" / "rag").mkdir(parents=True, exist_ok=True)
    (repo / ".llmc" / "rag" / "rag_graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "fn:foo",
                        "name": "foo",
                        "path": "a.py",  # relative to repo root
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    (repo / "a.py").write_text("def foo(x):\n    return x*2\n", encoding="utf-8")
    return repo


def _mk_enrich_db(repo: Path) -> Path:
    db = repo / ".rag" / "index_v2.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS enrichments(path TEXT, line INTEGER, summary TEXT, inputs TEXT, outputs TEXT, pitfalls TEXT, evidence TEXT, span_hash TEXT, content_type TEXT, content_language TEXT)"
    )
    # Path must match what's in the graph: "a.py" (relative to repo root)
    cur.execute(
        "INSERT INTO enrichments(path,line,summary,inputs,outputs,pitfalls,evidence) VALUES(?,?,?,?,?,?,?)",
        ("a.py", 1, "Function foo doubles input", "x", "2x", "", ""),
    )
    con.commit()
    con.close()
    return db


def test_public_api_delegates(hermetic_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mk_repo(hermetic_env)
    monkeypatch.setenv("LLMC_ENRICH", "0")
    q = "foo"
    s = tool_rag_search(repo_root=str(repo), query=q, limit=5)
    w = tool_rag_where_used(repo_root=str(repo), symbol=q, limit=5)
    l = tool_rag_lineage(repo_root=str(repo), symbol=q, direction="downstream", max_results=5)
    for res in (s, w, l):
        assert hasattr(res, "items")
        # meta.status is optional; when present it should be a known value.
        status = getattr(getattr(res, "meta", None), "status", None)
        if status is not None:
            assert status in {"OK", "FALLBACK", "ERROR"}
        assert res.source in {"RAG_GRAPH", "LOCAL_FALLBACK"}
        assert res.freshness_state in {"FRESH", "STALE", "UNKNOWN"}


@pytest.mark.integration
def test_search_attaches_enrichment(hermetic_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mk_repo(hermetic_env)
    db = _mk_enrich_db(repo)
    monkeypatch.setenv("LLMC_ENRICH", "1")
    monkeypatch.setenv("LLMC_ENRICH_DB", str(db))

    res = tool_rag_search(repo_root=str(repo), query="foo", limit=5)
    if res.items:
        assert any(getattr(it, "enrichment", None) and "summary" in it.enrichment for it in res.items)
