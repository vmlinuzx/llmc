from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    prompt_hash TEXT NOT NULL,
    route TEXT NOT NULL,
    provider TEXT,
    prompt TEXT NOT NULL,
    user_prompt TEXT,
    response TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    total_cost REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_unique
    ON entries(prompt_hash, route);

CREATE TABLE IF NOT EXISTS entry_vectors (
    entry_id INTEGER PRIMARY KEY,
    dim INTEGER NOT NULL,
    norm REAL NOT NULL,
    vec BLOB NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entry_route_created_at
    ON entries(route, created_at DESC);

CREATE TRIGGER IF NOT EXISTS trg_entries_updated_at
AFTER UPDATE ON entries
FOR EACH ROW
BEGIN
    UPDATE entries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""


class CacheDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    def upsert_entry(
        self,
        prompt_hash: str,
        route: str,
        provider: Optional[str],
        prompt: str,
        user_prompt: Optional[str],
        response: str,
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        total_cost: Optional[float],
    ) -> int:
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO entries (
                    prompt_hash, route, provider, prompt, user_prompt,
                    response, tokens_in, tokens_out, total_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt_hash,
                    route,
                    provider,
                    prompt,
                    user_prompt,
                    response,
                    tokens_in,
                    tokens_out,
                    total_cost,
                ),
            )
            row = self._conn.execute(
                "SELECT id FROM entries WHERE prompt_hash = ? AND route = ?",
                (prompt_hash, route),
            ).fetchone()
            return int(row[0])

    def insert_vector(self, entry_id: int, dim: int, norm: float, blob: bytes) -> None:
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO entry_vectors(entry_id, dim, norm, vec)
                VALUES (?, ?, ?, ?)
                """,
                (entry_id, dim, norm, sqlite3.Binary(blob)),
            )

    def delete_entry(self, entry_id: int) -> None:
        with self.transaction():
            self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
