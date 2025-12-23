from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sqlite3
import struct
import time

from .types import EnrichmentRecord, FileRecord, SpanRecord, SpanWorkItem

logger = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    lang TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    sidecar_path TEXT
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    slice_type TEXT,
    slice_language TEXT,
    classifier_confidence REAL,
    classifier_version TEXT,
    imports TEXT
);

CREATE TABLE IF NOT EXISTS embeddings_meta (
    profile TEXT NOT NULL DEFAULT 'default',
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (profile, model)
);

CREATE TABLE IF NOT EXISTS embeddings (
    span_hash TEXT PRIMARY KEY,
    vec BLOB NOT NULL,
    route_name TEXT,
    profile_name TEXT,
    FOREIGN KEY (span_hash) REFERENCES spans(span_hash) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS emb_code (
    span_hash TEXT PRIMARY KEY,
    vec BLOB NOT NULL,
    route_name TEXT,
    profile_name TEXT,
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
    content_type TEXT,
    content_language TEXT,
    content_type_confidence REAL,
    content_type_source TEXT,
    tokens_per_second REAL,
    eval_count INTEGER,
    eval_duration_ns INTEGER,
    prompt_eval_count INTEGER,
    total_duration_ns INTEGER,
    backend_host TEXT,
    FOREIGN KEY (span_hash) REFERENCES spans(span_hash) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_spans_file_id ON spans(file_id);
CREATE INDEX IF NOT EXISTS idx_spans_span_hash ON spans(span_hash);

CREATE TABLE IF NOT EXISTS file_descriptions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    file_path TEXT UNIQUE NOT NULL,
    description TEXT,
    source TEXT,
    updated_at DATETIME,
    content_hash TEXT,
    input_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_file_descriptions_file_path ON file_descriptions(file_path);
CREATE INDEX IF NOT EXISTS idx_file_descriptions_input_hash ON file_descriptions(input_hash);
"""

DB_SCHEMA_VERSION = 7


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._open_and_prepare()
        # _run_versioned_migrations is now called inside _open_and_prepare
        self._ensure_fts()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def repo_root(self) -> Path:
        """
        Infer repo root from database path.
        Assumes standard layout: <repo_root>/.llmc/rag/<db_name>
        """
        # Go up 3 levels: db -> rag -> .llmc -> repo_root
        return self.path.parent.parent.parent

    def get_span_by_hash(self, span_hash: str) -> SpanRecord | None:
        """Lookup a single span by its hash."""
        row = self.conn.execute(
            """
            SELECT
                s.span_hash,
                s.symbol,
                s.kind,
                s.start_line,
                s.end_line,
                s.byte_start,
                s.byte_end,
                s.slice_type,
                s.slice_language,
                s.classifier_confidence,
                s.classifier_version,
                s.imports,
                f.path AS file_path,
                f.lang AS lang
            FROM spans AS s
            JOIN files AS f ON f.id = s.file_id
            WHERE s.span_hash = ?
            """,
            (span_hash,),
        ).fetchone()

        if row is None:
            return None

        return SpanRecord(
            file_path=Path(row["file_path"]),
            lang=row["lang"],
            symbol=row["symbol"],
            kind=row["kind"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            byte_start=row["byte_start"],
            byte_end=row["byte_end"],
            span_hash=row["span_hash"],
            slice_type=row["slice_type"] or "other",
            slice_language=row["slice_language"],
            classifier_confidence=row["classifier_confidence"] or 0.0,
            classifier_version=row["classifier_version"] or "",
            imports=json.loads(row["imports"]) if row["imports"] else [],
        )

    def _get_existing_columns(self, table: str) -> set[str]:
        """Return set of column names for a table using PRAGMA table_info."""
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}  # column name is at index 1

    def _infer_schema_version(self, conn: sqlite3.Connection) -> int:
        """Infer schema version from column presence for legacy DBs."""

        def has_column(table: str, column: str) -> bool:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r[1] == column for r in rows)

        # Work backwards from latest to find highest matching version
        if has_column("spans", "imports"):
            return 7  # v7 added spans.imports
        if has_column("enrichments", "tokens_per_second"):
            return 6  # v6 added perf metrics
        if has_column("enrichments", "content_type"):
            return 5  # v5 added content_type
        if has_column("embeddings", "route_name"):
            return 4  # v4 added route_name
        if has_column("spans", "slice_type"):
            return 3  # v3 added slice_type
        if has_column("enrichments", "inputs"):
            return 2  # v2 added inputs/outputs
        return 1  # Base schema

    def _run_versioned_migrations(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Run only migrations needed to upgrade from from_version to current."""
        # Version 2: Added inputs/outputs/side_effects/pitfalls/usage_snippet
        if from_version < 2:
            migrations = [
                ("enrichments", "inputs", "TEXT"),
                ("enrichments", "outputs", "TEXT"),
                ("enrichments", "side_effects", "TEXT"),
                ("enrichments", "pitfalls", "TEXT"),
                ("enrichments", "usage_snippet", "TEXT"),
            ]
            for table, column, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                except sqlite3.OperationalError:
                    pass

        # Version 3: Added slice_type, slice_language, classifier_*
        if from_version < 3:
            migrations = [
                ("spans", "slice_type", "TEXT"),
                ("spans", "slice_language", "TEXT"),
                ("spans", "classifier_confidence", "REAL"),
                ("spans", "classifier_version", "TEXT"),
            ]
            for table, column, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                except sqlite3.OperationalError:
                    pass

        # Version 4: Added route_name, profile_name
        if from_version < 4:
            migrations = [
                ("embeddings", "route_name", "TEXT"),
                ("embeddings", "profile_name", "TEXT"),
            ]
            for table, column, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                except sqlite3.OperationalError:
                    pass

        # Version 5: Added content_type, content_language, etc.
        if from_version < 5:
            migrations = [
                ("enrichments", "content_type", "TEXT"),
                ("enrichments", "content_language", "TEXT"),
                ("enrichments", "content_type_confidence", "REAL"),
                ("enrichments", "content_type_source", "TEXT"),
            ]
            for table, column, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                except sqlite3.OperationalError:
                    pass

        # Version 6: Added performance metrics and sidecar_path
        if from_version < 6:
            migrations = [
                ("enrichments", "tokens_per_second", "REAL"),
                ("enrichments", "eval_count", "INTEGER"),
                ("enrichments", "eval_duration_ns", "INTEGER"),
                ("enrichments", "prompt_eval_count", "INTEGER"),
                ("enrichments", "total_duration_ns", "INTEGER"),
                ("enrichments", "backend_host", "TEXT"),
                ("files", "sidecar_path", "TEXT"),
            ]
            for table, column, coltype in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                except sqlite3.OperationalError:
                    pass

        # Version 7: Added spans.imports for dependency tracking
        if from_version < 7:
            try:
                conn.execute("ALTER TABLE spans ADD COLUMN imports TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Table migrations (for existing databases that predate certain tables)
        # file_descriptions: Added 2025-12 for stable file-level summaries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_descriptions (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                file_path TEXT UNIQUE NOT NULL,
                description TEXT,
                source TEXT,
                updated_at DATETIME,
                content_hash TEXT,
                input_hash TEXT
            )
        """)
        # Add input_hash column if not exists (for databases with old schema that
        # has the table but not the column - must be done BEFORE creating the index)
        try:
            conn.execute("ALTER TABLE file_descriptions ADD COLUMN input_hash TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_file_descriptions_file_path "
            "ON file_descriptions(file_path)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_file_descriptions_input_hash "
            "ON file_descriptions(input_hash)"
        )

    def close(self) -> None:
        self._conn.close()

    def vacuum(self) -> None:
        """Reclaim unused space in the database."""
        self._conn.execute("VACUUM")

    def _open_and_prepare(self) -> sqlite3.Connection:
        """Open the sqlite database with version-gated schema management."""
        attempts = 0
        while True:
            attempts += 1
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            try:
                current_version = conn.execute("PRAGMA user_version").fetchone()[0]

                if current_version == 0:
                    # Check if this is fresh DB or pre-gating legacy
                    tables = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                    if not tables or all(t[0].startswith("sqlite_") for t in tables):
                        # Fresh DB - apply latest schema directly
                        conn.executescript(SCHEMA)
                    else:
                        # Pre-gating legacy DB - infer version and migrate
                        inferred = self._infer_schema_version(conn)
                        self._run_versioned_migrations(conn, inferred)
                    conn.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
                elif current_version < DB_SCHEMA_VERSION:
                    # Post-gating DB - run only needed migrations
                    self._run_versioned_migrations(conn, current_version)
                    conn.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
                # else: current_version == DB_SCHEMA_VERSION, no action needed

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
        
        SAFETY: If new spans list is empty but existing spans exist, we preserve
        the existing spans. This guards against silent extractor failures that
        would otherwise nuke all enrichments for a file.
        """
        # Get existing span hashes for this file
        existing = self.conn.execute(
            "SELECT span_hash FROM spans WHERE file_id = ?", (file_id,)
        ).fetchall()
        existing_hashes = {row[0] for row in existing}
        
        # SAFETY GUARD: Don't delete existing spans if extractor returned empty
        # This prevents silent extractor failures from nuking enrichments
        if not spans and existing_hashes:
            # Get file path for better logging
            file_row = self.conn.execute(
                "SELECT path FROM files WHERE id = ?", (file_id,)
            ).fetchone()
            file_path = file_row[0] if file_row else f"file_id={file_id}"
            logger.warning(
                "Extractor returned 0 spans for %s, preserving %d existing spans",
                file_path,
                len(existing_hashes),
            )
            return  # Preserve existing spans, don't nuke them

        # New span hashes from the file
        new_hashes = {span.span_hash for span in spans}

        # Calculate the delta
        to_delete = existing_hashes - new_hashes  # Spans no longer in file
        to_add = new_hashes - existing_hashes  # New/modified spans
        unchanged = existing_hashes & new_hashes  # Preserved (with enrichments!)

        # Only delete spans that actually changed or were removed
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            self.conn.execute(
                f"DELETE FROM spans WHERE span_hash IN ({placeholders})", list(to_delete)
            )

        # Only insert truly new or modified spans
        new_spans = [s for s in spans if s.span_hash in to_add]
        if new_spans:
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO spans (
                    file_id, symbol, kind, start_line, end_line,
                    byte_start, byte_end, span_hash, doc_hint,
                    slice_type, slice_language, classifier_confidence, classifier_version,
                    imports
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        span.slice_type,
                        span.slice_language,
                        span.classifier_confidence,
                        span.classifier_version,
                        json.dumps(span.imports) if span.imports else None,
                    )
                    for span in new_spans
                ],
            )

        # Log the delta for visibility (helpful for debugging and metrics)
        if to_add or to_delete:
            logger.info(
                "Spans delta for file_id=%d: %d unchanged, %d added, %d deleted",
                file_id,
                len(unchanged),
                len(to_add),
                len(to_delete),
            )

    def get_file_hash(self, path: Path) -> str | None:
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
        """Fetch spans pending enrichment with O(1) random sampling.
        
        Uses ROWID-based random offset instead of ORDER BY RANDOM() to avoid
        O(N log N) sort on large tables. For small pending counts, falls back
        to sequential order which is fast enough.
        """
        import random
        
        # First, get the count and ROWID range of pending spans
        # This is a fast indexed query
        count_row = self.conn.execute(
            """
            SELECT COUNT(*), MIN(spans.id), MAX(spans.id)
            FROM spans
            LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
            WHERE enrichments.span_hash IS NULL
            """
        ).fetchone()
        
        pending_count = count_row[0] or 0
        min_id = count_row[1] or 0
        max_id = count_row[2] or 0
        
        if pending_count == 0:
            return []
        
        # For small pending counts, just fetch sequentially - no need for randomization
        # The overhead of random sampling isn't worth it for < 500 items
        if pending_count <= 500 or pending_count <= limit * 3:
            rows = self.conn.execute(
                """
                SELECT spans.span_hash, files.path, files.lang, spans.start_line,
                       spans.end_line, spans.byte_start, spans.byte_end, files.mtime,
                       spans.slice_type, spans.slice_language, spans.classifier_confidence
                FROM spans
                JOIN files ON spans.file_id = files.id
                LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
                WHERE enrichments.span_hash IS NULL
                ORDER BY spans.id
                LIMIT ?
                """,
                (limit * 2,),  # Slight overfetch for cooldown filtering
            ).fetchall()
        else:
            # Large pending set: use random ROWID offset sampling
            # Generate random starting offsets within the ROWID range
            # This gives O(1) random access instead of O(N log N) sort
            id_range = max_id - min_id + 1
            
            # Sample multiple random offsets to increase diversity
            sample_offsets = sorted(set(
                min_id + random.randint(0, id_range - 1) 
                for _ in range(min(limit * 4, 200))
            ))
            
            # Fetch spans near our random offsets using indexed lookups
            # Use UNION of small range queries for efficiency
            rows = []
            batch_size = max(10, limit // 4)
            
            for offset_id in sample_offsets[:20]:  # Limit offset probes
                if len(rows) >= limit * 2:
                    break
                    
                batch_rows = self.conn.execute(
                    """
                    SELECT spans.span_hash, files.path, files.lang, spans.start_line,
                           spans.end_line, spans.byte_start, spans.byte_end, files.mtime,
                           spans.slice_type, spans.slice_language, spans.classifier_confidence
                    FROM spans
                    JOIN files ON spans.file_id = files.id
                    LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
                    WHERE enrichments.span_hash IS NULL AND spans.id >= ?
                    ORDER BY spans.id
                    LIMIT ?
                    """,
                    (offset_id, batch_size),
                ).fetchall()
                rows.extend(batch_rows)
            
            # Shuffle the collected rows to avoid clustering
            random.shuffle(rows)
        
        now = time.time()
        filtered: list[SpanWorkItem] = []
        seen_hashes: set[str] = set()  # Deduplicate across batches
        
        for row in rows:
            span_hash = row["span_hash"]
            if span_hash in seen_hashes:
                continue
            seen_hashes.add(span_hash)
            
            if cooldown_seconds:
                mtime = row["mtime"] or 0
                if now - mtime < cooldown_seconds:
                    continue
            filtered.append(
                SpanWorkItem(
                    span_hash=span_hash,
                    file_path=Path(row["path"]),
                    lang=row["lang"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    byte_start=row["byte_start"],
                    byte_end=row["byte_end"],
                    slice_type=row["slice_type"] or "other",
                    slice_language=row["slice_language"],
                    classifier_confidence=row["classifier_confidence"] or 0.0,
                )
            )
            if len(filtered) == limit:
                break
        return filtered

    def store_enrichment(self, span_hash: str, payload: dict, meta: dict | None = None) -> None:
        """Store enrichment with optional performance metrics.
        
        Args:
            span_hash: Unique identifier for the span
            payload: Enrichment data from LLM (summary, tags, evidence, etc.)
            meta: Optional performance metrics from backend (tokens_per_second, eval_count, etc.)
        """
        meta = meta or {}
        self.conn.execute(
            """
            INSERT OR REPLACE INTO enrichments (
                span_hash, summary, tags, evidence, model, created_at, schema_ver,
                inputs, outputs, side_effects, pitfalls, usage_snippet,
                content_type, content_language, content_type_confidence, content_type_source,
                tokens_per_second, eval_count, eval_duration_ns, prompt_eval_count,
                total_duration_ns, backend_host
            ) VALUES (?, ?, ?, ?, ?, strftime('%s','now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_hash,
                payload.get("summary_120w") or payload.get("summary"),
                ",".join(payload.get("tags", [])) if payload.get("tags") else None,
                json.dumps(payload.get("evidence", [])),
                payload.get("model") or meta.get("model"),
                payload.get("schema_version"),
                json.dumps(payload.get("inputs", [])),
                json.dumps(payload.get("outputs", [])),
                json.dumps(payload.get("side_effects", [])),
                json.dumps(payload.get("pitfalls", [])),
                payload.get("usage_snippet"),
                payload.get("content_type"),
                payload.get("content_language"),
                payload.get("content_type_confidence"),
                payload.get("content_type_source"),
                # Performance metrics from Ollama
                meta.get("tokens_per_second"),
                meta.get("eval_count"),
                meta.get("eval_duration"),  # eval_duration is in ns
                meta.get("prompt_eval_count"),
                meta.get("total_duration"),  # total_duration is in ns
                meta.get("host") or meta.get("backend_host"),
            ),
        )

    def pending_embeddings(self, limit: int = 32) -> list[SpanWorkItem]:
        rows = self.conn.execute(
            """
            SELECT spans.span_hash, files.path, files.lang, spans.start_line,
                   spans.end_line, spans.byte_start, spans.byte_end, spans.slice_type,
                   spans.symbol
            FROM spans
            JOIN files ON spans.file_id = files.id
            LEFT JOIN embeddings ON spans.span_hash = embeddings.span_hash
            LEFT JOIN emb_code ON spans.span_hash = emb_code.span_hash
            WHERE embeddings.span_hash IS NULL AND emb_code.span_hash IS NULL
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
                slice_type=row["slice_type"] or "other",
                symbol=row["symbol"],
            )
            for row in rows
        ]

    def ensure_embedding_meta(self, model: str, dim: int, profile: str = "default") -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings_meta(profile, model, dim, created_at)
            VALUES (?, ?, ?, strftime('%s','now'))
            ON CONFLICT(profile, model) DO UPDATE SET
                dim = excluded.dim,
                created_at = excluded.created_at
            """,
            (profile, model, dim),
        )

    def store_embedding(
        self,
        span_hash: str,
        vector: list[float],
        route_name: str = "docs",
        profile_name: str = "default",
        table_name: str = "embeddings",
    ) -> None:
        blob = struct.pack(f"<{len(vector)}f", *vector)
        if table_name not in ("embeddings", "emb_code"):
            raise ValueError(f"Invalid table_name: {table_name}")

        self.conn.execute(
            f"""
            INSERT OR REPLACE INTO {table_name}(span_hash, vec, route_name, profile_name)
            VALUES (?, ?, ?, ?)
            """,
            (span_hash, sqlite3.Binary(blob), route_name, profile_name),
        )

    def iter_embeddings(self, table_name: str = "embeddings") -> Iterator[sqlite3.Row]:
        """Yield embedding rows joined with span/file metadata."""
        if table_name not in ("embeddings", "emb_code"):
            raise ValueError(f"Invalid table_name: {table_name}")

        cursor = self.conn.execute(
            f"""
            SELECT
                spans.span_hash,
                spans.symbol,
                spans.kind,
                spans.start_line,
                spans.end_line,
                files.path AS file_path,
                COALESCE(enrichments.summary, spans.doc_hint, '') AS summary,
                {table_name}.vec,
                {table_name}.route_name,
                {table_name}.profile_name
            FROM {table_name}
            JOIN spans ON spans.span_hash = {table_name}.span_hash
            JOIN files ON files.id = spans.file_id
            LEFT JOIN enrichments ON enrichments.span_hash = spans.span_hash
            """
        )
        yield from cursor

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
            # CRITICAL: Use unicode61 tokenizer to avoid stopwords!
            # FTS5's default 'porter' tokenizer includes English stopwords like
            # "model", "system", "data" which are fundamental to ML/AI codebases.
            # The 'unicode61' tokenizer has NO stopword list, making it suitable
            # for technical documentation and code search.
            # See: https://www.sqlite.org/fts5.html#unicode61_tokenizer
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts
                USING fts5(
                    symbol,
                    summary,
                    path,
                    start_line,
                    end_line,
                    tokenize='unicode61'
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
                s.slice_type,
                s.slice_language,
                s.classifier_confidence,
                s.classifier_version,
                s.imports,
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
                slice_type=row["slice_type"] or "other",
                slice_language=row["slice_language"],
                classifier_confidence=row["classifier_confidence"] or 0.0,
                classifier_version=row["classifier_version"] or "",
                imports=json.loads(row["imports"]) if row["imports"] else [],
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

    def fetch_enrichment_by_span_hash(self, span_hash: str) -> EnrichmentRecord | None:
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

    def fetch_enrichment_by_symbol(self, symbol: str) -> EnrichmentRecord | None:
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
                INSERT INTO enrichments_fts(rowid, symbol, summary, path, start_line, end_line)
                SELECT e.rowid, s.symbol, e.summary, f.path, s.start_line, s.end_line
                FROM enrichments AS e
                JOIN spans AS s ON s.span_hash = e.span_hash
                JOIN files AS f ON f.id = s.file_id
                """
            )
            row = conn.execute("SELECT COUNT(*) AS n FROM enrichments_fts").fetchone()
        return int(row["n"]) if row is not None else 0

    def search_enrichments_fts(
        self, query: str, limit: int = 10
    ) -> list[tuple[str, str | None, float | None]]:
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

        results: list[tuple[str, str | None, float | None]] = []
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
