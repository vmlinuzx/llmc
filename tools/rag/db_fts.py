from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

DEFAULT_DB_CANDIDATES = [".rag/index_v2.db", ".rag/index.db", ".rag/index.db3"]


@dataclass
class FtsHit:
    file: str
    start_line: int
    end_line: int
    text: str
    score: float  # raw bm25 (lower is better) or 0.0 if unavailable


class RagDbNotFound(FileNotFoundError):
    """Raised when no suitable RAG DB file can be found."""


def _open_db(repo_root: Path, explicit: Path | None = None) -> tuple[sqlite3.Connection, Path]:
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

    def score(name_sql: tuple[str, str]) -> int:
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


def _column_map(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """Map logical fields -> physical column names via common-name heuristics."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1].lower() for r in cur.fetchall()]

    def pick(*candidates: str, default: str | None = None) -> str:
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
    repo_root: Path, query: str, limit: int = 20, db_path: Path | None = None
) -> list[FtsHit]:
    """Run an FTS MATCH search against the enrichment DB with optional bm25 ordering."""
    conn, path = _open_db(repo_root, db_path)
    try:
        table = _detect_fts_table(conn)
        col = _column_map(conn, table)

        cur = conn.cursor()
        sql_bm25 = f"""
            SELECT {col["path"]} as path,
                   COALESCE({col["start"]}, 1) as start_line,
                   COALESCE({col["end"]},   COALESCE({col["start"]},1)+1) as end_line,
                   {col["text"]} as text,
                   bm25({table}) as score
            FROM {table}
            WHERE {table} MATCH ?
            ORDER BY score ASC
            LIMIT ?
        """
        try:
            cur.execute(sql_bm25, (query, int(limit)))
            rows = cur.fetchall()
        except Exception:
            sql = f"""
                SELECT {col["path"]} as path,
                       COALESCE({col["start"]}, 1) as start_line,
                       COALESCE({col["end"]},   COALESCE({col["start"]},1)+1) as end_line,
                       {col["text"]} as text
                FROM {table}
                WHERE {table} MATCH ?
                LIMIT ?
            """
            cur.execute(sql, (query, int(limit)))
            rows = [(*r, 0.0) for r in cur.fetchall()]

        hits: list[FtsHit] = []
        for p, s, e, t, sc in rows:
            hits.append(
                FtsHit(
                    file=str(p),
                    start_line=int(s or 1),
                    end_line=int(e or (s or 1) + 1),
                    text=str(t or ""),
                    score=float(sc or 0.0),
                )
            )
        return hits
    finally:
        conn.close()
