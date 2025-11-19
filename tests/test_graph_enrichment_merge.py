import sqlite3
from pathlib import Path

import pytest

from tools.rag.graph_enrich import enrich_graph_entities


class _Ent:
    def __init__(self, path: str, start: int, end: int) -> None:
        self.path = path
        self.start_line = start
        self.end_line = end
        self.metadata: dict = {}


class _Graph:
    def __init__(self, entities: list[_Ent]) -> None:
        self.entities = entities


def _make_db(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir(exist_ok=True)
    db_path = repo / ".rag" / "index_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS enrichments(path TEXT, line INTEGER, summary TEXT, inputs TEXT, outputs TEXT, pitfalls TEXT, evidence TEXT)"
    )
    cur.execute(
        "INSERT INTO enrichments VALUES(?,?,?,?,?,?,?)",
        ("src/a.py", 10, "sum-a", "in-a", "out-a", "pit-a", "ev-a"),
    )
    con.commit()
    con.close()
    return db_path


def test_enrich_graph_entities_merges_into_metadata(hermetic_env: Path) -> None:
    repo = hermetic_env / "repo"
    repo.mkdir(exist_ok=True)
    _make_db(hermetic_env)

    ent_match = _Ent(str(repo / "src" / "a.py"), 10, 12)
    ent_miss = _Ent(str(repo / "src" / "b.py"), 1, 1)
    graph = _Graph([ent_match, ent_miss])

    # Default LLMC_ENRICH behavior should be treated as enabled in test harness.
    enrich_graph_entities(graph, repo)

    assert "enrichment" in ent_match.metadata
    assert ent_match.metadata["enrichment"]["summary"] == "sum-a"
    assert "__enrich_meta" in ent_match.metadata
    assert "enrichment" not in ent_miss.metadata
