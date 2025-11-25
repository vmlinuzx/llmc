from __future__ import annotations

import sqlite3
import struct
from contextlib import contextmanager
import time
from pathlib import Path
from typing import Optional
from collections.abc import Iterable, Iterator, Sequence

import json

from .types import FileRecord, SpanRecord, SpanWorkItem, EnrichmentRecord

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
        self._conn = self._open_and_prepare()
        self._run_migrations()
        self._ensure_fts()

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

    def _open_and_prepare(self) -> sqlite3.Connection:
        """Open the sqlite database, quarantining corrupt files if needed."""
        attempts = 0
        while True:
            attempts += 1
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            try:
                conn.executescript(SCHEMA)
            except sqlite3.DatabaseError as exc:
                conn.close()
                if not self._should_recover_from(exc) or attempts >= 2:
                    raise
                self._quarantine_corrupt_db()
                continue
            return conn

    def _should_recover_from(self, exc: sqlite3.DatabaseError) -> bool:
        message = str(exc).lower()
        if "file is not a database" in message:
            return True
        if "database disk image is malformed" in message:
            return True
        return False

    def _quarantine_corrupt_db(self) -> None:
        if not self.path.exists():
            return
        timestamp = int(time.time())
        suffix = f".corrupt.{timestamp}"
        quarantine_path = self.path.with_name(f"{self.path.name}{suffix}")
        try:
            self.path.replace(quarantine_path)
        except OSError:
            # If rename fails we leave the original file in place and re-raise.
            raise

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

    def replace_spans(self, file_id: int, spans: Sequence[SpanRecord]) -> None:
        """Replace spans for a file, preserving unchanged spans and their enrichments.
        
        This is a DIFFERENTIAL update:
        - Keeps spans with unchanged content (same span_hash)
        - Only deletes spans that were removed or changed
        - Only inserts new or modified spans
        
        This preserves enrichments for unchanged code, saving 90%+ LLM calls!
        """
        # Get existing span hashes for this file
        existing = self.conn.execute(
            "SELECT span_hash FROM spans WHERE file_id = ?",
            (file_id,)
        ).fetchall()
        existing_hashes = {row[0] for row in existing}
        
        # New span hashes from the file
        new_hashes = {span.span_hash for span in spans}
        
        # Calculate the delta
        to_delete = existing_hashes - new_hashes  # Spans no longer in file
        to_add = new_hashes - existing_hashes      # New/modified spans
        unchanged = existing_hashes & new_hashes   # Preserved (with enrichments!)
        
        # Only delete spans that actually changed or were removed
        if to_delete:
            placeholders = ','.join('?' * len(to_delete))
            self.conn.execute(
                f"DELETE FROM spans WHERE span_hash IN ({placeholders})",
                list(to_delete)
            )
        
        # Only insert truly new or modified spans
        new_spans = [s for s in spans if s.span_hash in to_add]
        if new_spans:
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
                    for span in new_spans
                ],
            )
        
        # Log the delta for visibility (helpful for debugging and metrics)
        if to_add or to_delete:
            import sys
            print(f"    📊 Spans: {len(unchanged)} unchanged, {len(to_add)} added, {len(to_delete)} deleted", file=sys.stderr)

    def get_file_hash(self, path: Path) -> Optional[str]:
        """Get the stored file hash for a given path.
        
        Returns:
            The file hash if the file exists in the database, None otherwise.
        """
        row = self.conn.execute(
            "SELECT file_hash FROM files WHERE path = ?",
            (str(path),),
        ).fetchone()
        return row[0] if row else None

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

    def iter_embeddings(self) -> Iterator[sqlite3.Row]:
        """Yield embedding rows joined with span/file metadata."""
        cursor = self.conn.execute(
            """
            SELECT
                spans.span_hash,
                spans.symbol,
                spans.kind,
                spans.start_line,
                spans.end_line,
                files.path AS file_path,
                COALESCE(enrichments.summary, spans.doc_hint, '') AS summary,
                embeddings.vec
            FROM embeddings
            JOIN spans ON spans.span_hash = embeddings.span_hash
            JOIN files ON files.id = spans.file_id
            LEFT JOIN enrichments ON enrichments.span_hash = spans.span_hash
            """
        )
        for row in cursor:
            yield row


    # ------------------------------------------------------------------
    # Enrichment-aware helpers (Phase 1 – DB / FTS integration)
    # ------------------------------------------------------------------

    def _ensure_fts(self) -> None:
        """
        Ensure the optional FTS5 virtual table for enrichments exists.

        This method is intentionally defensive: if FTS5 is unavailable in the
        SQLite build, the database remains usable but FTS-backed search will be
        disabled (fts_available == False).
        """
        self._fts_available = False
        try:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts
                USING fts5(
                    symbol,
                    summary
                )
                """
            )
        except sqlite3.OperationalError as exc:
            # Gracefully degrade on SQLite builds without FTS5 support.
            msg = str(exc).lower()
            if "fts5" in msg:
                self._fts_available = False
            else:
                raise
        else:
            self._fts_available = True

    @property
    def fts_available(self) -> bool:
        """Return True if the enrichments_fts virtual table is available."""
        return bool(getattr(self, "_fts_available", False))

    # -- Span / enrichment projection helpers ---------------------------------

    def fetch_all_spans(self) -> list[SpanRecord]:
        """Return all spans joined with their file metadata.

        This is a read-only helper used by schema/graph builders to project the
        spans table into a typed, in-memory representation.
        """
        rows = self.conn.execute(
            """
            SELECT
                s.span_hash,
                s.symbol,
                s.kind,
                s.start_line,
                s.end_line,
                s.byte_start,
                s.byte_end,
                f.path AS file_path,
                f.lang AS lang
            FROM spans AS s
            JOIN files AS f ON f.id = s.file_id
            """
        ).fetchall()
        return [
            SpanRecord(
                file_path=Path(row["file_path"]),
                lang=row["lang"],
                symbol=row["symbol"],
                kind=row["kind"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                byte_start=row["byte_start"],
                byte_end=row["byte_end"],
                span_hash=row["span_hash"],
            )
            for row in rows
        ]

    def fetch_all_enrichments(self) -> list[EnrichmentRecord]:
        """Return all enrichment rows joined with their span symbol."""
        rows = self.conn.execute(
            """
            SELECT
                e.span_hash,
                s.symbol AS symbol,
                e.summary,
                e.evidence,
                e.inputs,
                e.outputs,
                e.side_effects,
                e.pitfalls,
                e.usage_snippet,
                e.tags,
                e.model,
                e.created_at,
                e.schema_ver
            FROM enrichments AS e
            JOIN spans AS s ON s.span_hash = e.span_hash
            """
        ).fetchall()
        return [r for r in (self._row_to_enrichment(row) for row in rows) if r is not None]

    def fetch_enrichment_by_span_hash(self, span_hash: str) -> Optional[EnrichmentRecord]:
        """Lookup a single enrichment row by span_hash."""
        row = self.conn.execute(
            """
            SELECT
                e.span_hash,
                s.symbol AS symbol,
                e.summary,
                e.evidence,
                e.inputs,
                e.outputs,
                e.side_effects,
                e.pitfalls,
                e.usage_snippet,
                e.tags,
                e.model,
                e.created_at,
                e.schema_ver
            FROM enrichments AS e
            JOIN spans AS s ON s.span_hash = e.span_hash
            WHERE e.span_hash = ?
            """,
            (span_hash,),
        ).fetchone()
        return self._row_to_enrichment(row) if row is not None else None

    def fetch_enrichment_by_symbol(self, symbol: str) -> Optional[EnrichmentRecord]:
        """Lookup a single enrichment row by fully-qualified symbol."""
        row = self.conn.execute(
            """
            SELECT
                e.span_hash,
                s.symbol AS symbol,
                e.summary,
                e.evidence,
                e.inputs,
                e.outputs,
                e.side_effects,
                e.pitfalls,
                e.usage_snippet,
                e.tags,
                e.model,
                e.created_at,
                e.schema_ver
            FROM enrichments AS e
            JOIN spans AS s ON s.span_hash = e.span_hash
            WHERE s.symbol = ?
            """,
            (symbol,),
        ).fetchone()
        return self._row_to_enrichment(row) if row is not None else None

    def _row_to_enrichment(self, row: sqlite3.Row | None) -> EnrichmentRecord | None:
        """Internal helper to map a sqlite row into EnrichmentRecord."""
        if row is None:
            return None
        return EnrichmentRecord(
            span_hash=row["span_hash"],
            symbol=row["symbol"],
            summary=row["summary"],
            evidence=row["evidence"],
            inputs=row["inputs"],
            outputs=row["outputs"],
            side_effects=row["side_effects"],
            pitfalls=row["pitfalls"],
            usage_snippet=row["usage_snippet"],
            tags=row["tags"],
            model=row["model"],
            created_at=row["created_at"],
            schema_ver=row["schema_ver"],
        )

    # -- FTS-backed search helpers --------------------------------------------

    def rebuild_enrichments_fts(self) -> int:
        """Rebuild the enrichments_fts virtual table from current data.

        Returns the number of rows in the FTS table after rebuild. If FTS is
        not available, this is a no-op that returns 0.
        """
        if not self.fts_available:
            return 0

        with self.transaction() as conn:
            conn.execute("DELETE FROM enrichments_fts")
            conn.execute(
                """
                INSERT INTO enrichments_fts(rowid, symbol, summary)
                SELECT e.rowid, s.symbol, e.summary
                FROM enrichments AS e
                JOIN spans AS s ON s.span_hash = e.span_hash
                """
            )
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM enrichments_fts"
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    def search_enrichments_fts(self, query: str, limit: int = 10) -> list[tuple[str, Optional[str], Optional[float]]]:
        """Search enrichments text using FTS5.

        Returns:
            A list of (symbol, summary, score) tuples ordered by relevance.
            The score is bm25() if available, otherwise None.
        """
        if not self.fts_available:
            return []

        try:
            rows = self.conn.execute(
                """
                SELECT
                    symbol,
                    summary,
                    bm25(enrichments_fts) AS score
                FROM enrichments_fts
                WHERE enrichments_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            # Graceful fallback if bm25() is unavailable.
            if "no such function: bm25" in str(exc).lower():
                rows = self.conn.execute(
                    """
                    SELECT
                        symbol,
                        summary,
                        NULL AS score
                    FROM enrichments_fts
                    WHERE enrichments_fts MATCH ?
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            else:
                raise

        results: list[tuple[str, Optional[str], Optional[float]]] = []
        for row in rows:
            score_val = row["score"]
            score = float(score_val) if score_val is not None else None
            results.append((row["symbol"], row["summary"], score))
        return results


    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
