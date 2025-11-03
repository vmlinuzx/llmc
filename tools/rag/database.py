from __future__ import annotations

import sqlite3
import struct
from contextlib import contextmanager
import time
from pathlib import Path
from typing import Iterable, Iterator

import json

from .types import FileRecord, SpanRecord, SpanWorkItem

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    lang TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS spans (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    byte_start INTEGER NOT NULL,
    byte_end INTEGER NOT NULL,
    span_hash TEXT NOT NULL UNIQUE,
    doc_hint TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS embeddings_meta (
    model TEXT PRIMARY KEY,
    dim INTEGER NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    span_hash TEXT PRIMARY KEY,
    vec BLOB NOT NULL,
    FOREIGN KEY (span_hash) REFERENCES spans(span_hash) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrichments (
    span_hash TEXT PRIMARY KEY,
    summary TEXT,
    tags TEXT,
    evidence TEXT,
    model TEXT,
    created_at DATETIME,
    schema_ver TEXT,
    inputs TEXT,
    outputs TEXT,
    side_effects TEXT,
    pitfalls TEXT,
    usage_snippet TEXT,
    FOREIGN KEY (span_hash) REFERENCES spans(span_hash) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_spans_file_id ON spans(file_id);
CREATE INDEX IF NOT EXISTS idx_spans_span_hash ON spans(span_hash);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._run_migrations()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def _run_migrations(self) -> None:
        migrations = [
            ("enrichments", "inputs", "TEXT"),
            ("enrichments", "outputs", "TEXT"),
            ("enrichments", "side_effects", "TEXT"),
            ("enrichments", "pitfalls", "TEXT"),
            ("enrichments", "usage_snippet", "TEXT"),
        ]
        for table, column, coltype in migrations:
            try:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            except sqlite3.OperationalError:
                pass

    def close(self) -> None:
        self._conn.close()

    def upsert_file(self, record: FileRecord) -> int:
        self.conn.execute(
            """
            INSERT INTO files(path, lang, file_hash, size, mtime)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                lang = excluded.lang,
                file_hash = excluded.file_hash,
                size = excluded.size,
                mtime = excluded.mtime
            """,
            (str(record.path), record.lang, record.file_hash, record.size, record.mtime),
        )
        row = self.conn.execute(
            "SELECT id FROM files WHERE path = ?",
            (str(record.path),),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve file id for {record.path}")
        return int(row[0])

    def replace_spans(self, file_id: int, spans: Iterable[SpanRecord]) -> None:
        self.conn.execute("DELETE FROM spans WHERE file_id = ?", (file_id,))
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO spans (
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, doc_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    file_id,
                    span.symbol,
                    span.kind,
                    span.start_line,
                    span.end_line,
                    span.byte_start,
                    span.byte_end,
                    span.span_hash,
                    span.doc_hint,
                )
                for span in spans
            ],
        )

    def delete_file(self, path: Path) -> None:
        self.conn.execute("DELETE FROM files WHERE path = ?", (str(path),))

    def remove_missing_spans(self, valid_span_hashes: Iterable[str]) -> None:
        placeholders = ",".join("?" for _ in valid_span_hashes)
        if not placeholders:
            return
        query = f"DELETE FROM spans WHERE span_hash NOT IN ({placeholders})"
        self.conn.execute(query, list(valid_span_hashes))

    def stats(self) -> dict:
        files = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        spans = self.conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        enrichments = self.conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        embeddings = self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        return {
            "files": files,
            "spans": spans,
            "embeddings": embeddings,
            "enrichments": enrichments,
        }

    def pending_enrichments(self, limit: int = 32, cooldown_seconds: int = 0) -> list[SpanWorkItem]:
        candidate_limit = max(limit * 5, limit)
        rows = self.conn.execute(
            """
            SELECT spans.span_hash, files.path, files.lang, spans.start_line,
                   spans.end_line, spans.byte_start, spans.byte_end, files.mtime
            FROM spans
            JOIN files ON spans.file_id = files.id
            LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
            WHERE enrichments.span_hash IS NULL
            ORDER BY spans.id
            LIMIT ?
            """,
            (candidate_limit,),
        ).fetchall()
        now = time.time()
        filtered: list[SpanWorkItem] = []
        for row in rows:
            if cooldown_seconds:
                mtime = row["mtime"] or 0
                if now - mtime < cooldown_seconds:
                    continue
            filtered.append(
                SpanWorkItem(
                    span_hash=row["span_hash"],
                    file_path=Path(row["path"]),
                    lang=row["lang"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    byte_start=row["byte_start"],
                    byte_end=row["byte_end"],
                )
            )
            if len(filtered) == limit:
                break
        return filtered

    def store_enrichment(self, span_hash: str, payload: dict) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO enrichments (
                span_hash, summary, tags, evidence, model, created_at, schema_ver,
                inputs, outputs, side_effects, pitfalls, usage_snippet
            ) VALUES (?, ?, ?, ?, ?, strftime('%s','now'), ?, ?, ?, ?, ?, ?)
            """,
            (
                span_hash,
                payload.get("summary_120w"),
                ",".join(payload.get("tags", [])) if payload.get("tags") else None,
                json.dumps(payload.get("evidence", [])),
                payload.get("model"),
                payload.get("schema_version"),
                json.dumps(payload.get("inputs", [])),
                json.dumps(payload.get("outputs", [])),
                json.dumps(payload.get("side_effects", [])),
                json.dumps(payload.get("pitfalls", [])),
                payload.get("usage_snippet"),
            ),
        )

    def pending_embeddings(self, limit: int = 32) -> list[SpanWorkItem]:
        rows = self.conn.execute(
            """
            SELECT spans.span_hash, files.path, files.lang, spans.start_line,
                   spans.end_line, spans.byte_start, spans.byte_end
            FROM spans
            JOIN files ON spans.file_id = files.id
            LEFT JOIN embeddings ON spans.span_hash = embeddings.span_hash
            WHERE embeddings.span_hash IS NULL
            ORDER BY spans.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            SpanWorkItem(
                span_hash=row["span_hash"],
                file_path=Path(row["path"]),
                lang=row["lang"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                byte_start=row["byte_start"],
                byte_end=row["byte_end"],
            )
            for row in rows
        ]

    def ensure_embedding_meta(self, model: str, dim: int) -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings_meta(model, dim, created_at)
            VALUES (?, ?, strftime('%s','now'))
            ON CONFLICT(model) DO UPDATE SET
                dim = excluded.dim,
                created_at = excluded.created_at
            """,
            (model, dim),
        )

    def store_embedding(self, span_hash: str, vector: list[float]) -> None:
        blob = struct.pack(f"<{len(vector)}f", *vector)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO embeddings(span_hash, vec)
            VALUES (?, ?)
            """,
            (span_hash, sqlite3.Binary(blob)),
        )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
