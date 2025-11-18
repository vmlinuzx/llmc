from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_CANDIDATES = [".rag/index_v2.db", ".rag/index.db", ".rag/index.db3"]


@dataclass
class FtsHit:
    file: str
    start_line: int
    end_line: int
    text: str
    score: float


class RagDbNotFound(FileNotFoundError):
    """Raised when no suitable RAG DB file can be found."""


def _open_db(repo_root: Path, explicit: Optional[Path] = None) -> Tuple[sqlite3.Connection, Path]:
    """Open the RAG SQLite DB; try common locations."""
    if explicit:
        db_path = explicit
        if not db_path.exists():
            raise RagDbNotFound(str(db_path))
        return sqlite3.connect(str(db_path)), db_path

    for rel in DEFAULT_DB_CANDIDATES:
        db_path = (repo_root / rel).resolve()
        if db_path.exists():
            return sqlite3.connect(str(db_path)), db_path
    raise RagDbNotFound("No RAG DB found (.rag/index_v2.db | .rag/index.db | .rag/index.db3)")


def _detect_fts_table(conn: sqlite3.Connection) -> str:
    """Return an FTS table name by inspecting sqlite_master."""
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    rows = cur.fetchall()

    candidates = []
    for name, sql in rows:
        s = (sql or "").lower()
        if "using fts5" in s or "using fts4" in s or "using fts3" in s:
            candidates.append((name, s))

    preference = ["spans", "chunks", "documents", "enrichments"]

    def score(name_sql: Tuple[str, str]) -> int:
        name, _ = name_sql
        pts = 0
        for i, tok in enumerate(preference):
            if tok in name.lower():
                pts += 10 - i
        return pts

    if candidates:
        candidates.sort(key=score, reverse=True)
        return candidates[0][0]

    for name, sql in rows:
        s = (sql or "").lower()
        if "match" in s or "fts" in s:
            return name

    raise RuntimeError("No FTS virtual table detected in SQLite DB")


def _column_map(conn: sqlite3.Connection, table: str) -> Dict[str, str]:
    """Map logical fields -> physical column names via common-name heuristics."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1].lower() for r in cur.fetchall()]

    def pick(*candidates: str, default: Optional[str] = None) -> str:
        for c in candidates:
            if c in cols:
                return c
        if default is not None:
            return default
        raise RuntimeError(f"Required column not found in {table}: one of {candidates}")

    path_col = pick("path", "file", "filepath", "relpath")
    start_col = pick("start_line", "start", "line_start", "lineno", default=None) or "start_line"
    end_col = pick("end_line", "end", "line_end", "lineno_end", default=None) or "end_line"
    text_col = pick("text", "content", "body", "span_text")
    return {"path": path_col, "start": start_col, "end": end_col, "text": text_col}


def fts_search(
    repo_root: Path,
    query: str,
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> List[FtsHit]:
    """Run an FTS MATCH search against the enrichment DB.

    Heuristics and defensive fallbacks let this work against slightly different
    table/column names without requiring a strict schema.
    """
    conn, path = _open_db(repo_root, db_path)
    try:
        table = _detect_fts_table(conn)
        col = _column_map(conn, table)
        sql = f"""
            SELECT {col['path']} as path,
                   COALESCE({col['start']}, 1) as start_line,
                   COALESCE({col['end']},   COALESCE({col['start']},1)+1) as end_line,
                   {col['text']} as text
            FROM {table}
            WHERE {table} MATCH ?
            LIMIT ?
        """
        cur = conn.cursor()
        cur.execute(sql, (query, int(limit)))
        rows = cur.fetchall()
        hits: List[FtsHit] = []
        for p, s, e, t in rows:
            start = int(s or 1)
            end = int(e or (s or 1) or 1)
            hits.append(
                FtsHit(
                    file=str(p),
                    start_line=start,
                    end_line=end,
                    text=str(t or ""),
                    score=0.0,
                )
            )
        return hits
    finally:
        conn.close()

