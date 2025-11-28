"""
Telemetry for Tool Envelope.

SQLite event log for Coach to consume and analyze.
Captures: command, output size, truncation, handle usage, latency.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import _find_repo_root, get_te_config


@dataclass
class TeEvent:
    """A telemetry event."""

    timestamp: str
    agent_id: str
    session_id: str
    cmd: str
    mode: str  # enriched | raw | passthrough | error
    input_size: int  # bytes of underlying output
    output_size: int  # bytes after TE processing
    truncated: bool
    handle_created: bool
    latency_ms: int
    error: str | None = None


def _now_iso() -> str:
    """UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _get_telemetry_db_path(repo_root: Path | None = None) -> Path:
    """Get telemetry database path, creating parent dirs if needed."""
    root = repo_root or _find_repo_root()
    # Store in .llmc/te_telemetry.db instead of JSONL
    path = root / ".llmc" / "te_telemetry.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _init_telemetry_db(db_path: Path) -> None:
    """Initialize telemetry database schema if needed."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                cmd TEXT NOT NULL,
                mode TEXT NOT NULL,
                input_size INTEGER NOT NULL,
                output_size INTEGER NOT NULL,
                truncated INTEGER NOT NULL,
                handle_created INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                error TEXT
            )
        """)
        
        # Index for common queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON telemetry_events(timestamp DESC)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_cmd 
            ON telemetry_events(agent_id, cmd)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mode 
            ON telemetry_events(mode)
        """)
        
        conn.commit()
    finally:
        conn.close()


def log_event(
    cmd: str,
    mode: str,
    input_size: int,
    output_size: int,
    truncated: bool,
    handle_created: bool,
    latency_ms: int,
    error: str | None = None,
    repo_root: Path | None = None,
) -> None:
    """Log a telemetry event to SQLite database."""
    cfg = get_te_config(repo_root)
    if not cfg.telemetry_enabled:
        return

    event = TeEvent(
        timestamp=_now_iso(),
        agent_id=os.getenv("TE_AGENT_ID", "unknown"),
        session_id=os.getenv("TE_SESSION_ID", "unknown"),
        cmd=cmd,
        mode=mode,
        input_size=input_size,
        output_size=output_size,
        truncated=truncated,
        handle_created=handle_created,
        latency_ms=latency_ms,
        error=error,
    )

    db_path = _get_telemetry_db_path(repo_root)
    
    try:
        _init_telemetry_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("""
                INSERT INTO telemetry_events (
                    timestamp, agent_id, session_id, cmd, mode,
                    input_size, output_size, truncated, handle_created,
                    latency_ms, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.timestamp,
                event.agent_id,
                event.session_id,
                event.cmd,
                event.mode,
                event.input_size,
                event.output_size,
                1 if event.truncated else 0,
                1 if event.handle_created else 0,
                event.latency_ms,
                event.error,
            ))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Telemetry should never break the tool
        pass


class TeTimer:
    """Context manager for timing TE operations."""

    def __init__(self) -> None:
        self.start_ns: int = 0
        self.elapsed_ms: int = 0

    def __enter__(self) -> "TeTimer":
        self.start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, *args) -> None:
        self.elapsed_ms = (time.perf_counter_ns() - self.start_ns) // 1_000_000
