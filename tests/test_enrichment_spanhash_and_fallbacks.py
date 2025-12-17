import hashlib
from pathlib import Path
import sqlite3

from llmc.rag_nav import models
from llmc.rag_nav.enrichment import (
    EnrichStats,
    SqliteEnrichmentStore,
    attach_enrichments_to_search_result,
)


def make_db_with_span(tmp_path: Path) -> tuple[Path, str]:
    db = tmp_path / "enrich_span.db"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS enrichments")
    cur.execute(
        "CREATE TABLE enrichments(span_hash TEXT, path TEXT, line INTEGER, summary TEXT, inputs TEXT, outputs TEXT, pitfalls TEXT, content_type TEXT, content_language TEXT)"
    )
    file = "repo/a.py".lower()
    start, end = 10, 12
    text = "def foo(x):\n    return x\n"
    key = "|".join([file, str(start), str(end), " ".join(text.split())]).encode()
    h = hashlib.sha1(key).hexdigest()
    cur.execute(
        "INSERT INTO enrichments VALUES(?,?,?,?,?,?,?,?,?)",
        (h, file, start, "sum-a", "in-a", "out-a", "pit-a", "code", "python"),
    )
    con.commit()
    con.close()
    return db, text


def test_spanhash_match_preferred(tmp_path):
    db, text = make_db_with_span(tmp_path)
    store = SqliteEnrichmentStore(db)
    loc = models.SnippetLocation(path="repo/a.py", start_line=10, end_line=12)
    snip = models.Snippet(text=text, location=loc)
    item = models.SearchItem(file="repo/a.py", snippet=snip)  # type: ignore
    res = models.SearchResult(query="q", items=[item], source="RAG_GRAPH", freshness_state="FRESH")  # type: ignore
    stats = EnrichStats()
    out = attach_enrichments_to_search_result(res, store, stats=stats)
    assert out.items[0].enrichment["summary"] == "sum-a"
    assert stats.span_matches == 1


def test_fallback_line_then_path(tmp_path):
    db = tmp_path / "enrich_line.db"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS enrichments")
    cur.execute(
        "CREATE TABLE enrichments(path TEXT, line INTEGER, summary TEXT, inputs TEXT, outputs TEXT, pitfalls TEXT, content_type TEXT, content_language TEXT)"
    )
    cur.execute(
        "INSERT INTO enrichments VALUES(?,?,?,?,?,?,?,?)",
        ("repo/b.py", 5, "sum-b", "in-b", "out-b", "pit-b", "code", "python"),
    )
    cur.execute(
        "INSERT INTO enrichments VALUES(?,?,?,?,?,?,?,?)",
        ("repo/c.py", 0, "sum-c", "in-c", "out-c", "pit-c", "code", "python"),
    )
    con.commit()
    con.close()

    store = SqliteEnrichmentStore(db)

    # Line match
    loc = models.SnippetLocation(path="repo/b.py", start_line=5, end_line=5)
    snip = models.Snippet(text="x", location=loc)
    item = models.SearchItem(file="repo/b.py", snippet=snip)  # type: ignore
    res = models.SearchResult(
        query="q", items=[item], source="RAG_GRAPH", freshness_state="UNKNOWN"
    )  # type: ignore
    stats = EnrichStats()
    out = attach_enrichments_to_search_result(res, store, stats=stats)
    assert out.items[0].enrichment["summary"] == "sum-b"
    assert stats.line_matches == 1

    # Path-only fallback
    loc2 = models.SnippetLocation(path="repo/c.py", start_line=99, end_line=99)
    snip2 = models.Snippet(text="y", location=loc2)
    item2 = models.SearchItem(file="repo/c.py", snippet=snip2)  # type: ignore
    res2 = models.SearchResult(
        query="q", items=[item2], source="RAG_GRAPH", freshness_state="UNKNOWN"
    )  # type: ignore
    out2 = attach_enrichments_to_search_result(res2, store)
    assert out2.items[0].enrichment["summary"] == "sum-c"
