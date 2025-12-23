"""
Enrichment Logger - Thread-safe, atomic JSONL logging for enrichment events.

This module provides structured logging for enrichment operations:
- Atomic writes with file locking for multi-process safety
- JSONL format for machine parsability
- Validation to prevent corrupt log entries

Usage:
    from llmc.rag.enrichment_logger import EnrichmentLogger
    
    logger = EnrichmentLogger(Path("logs"))
    logger.log_success(
        span_hash="abc123",
        file_path="src/main.py",
        duration_sec=2.5,
        model="qwen3:4b",
        meta={"tokens_per_second": 45.2}
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import json
import logging
from pathlib import Path
from typing import Any

# Standard library logger for internal errors
_logger = logging.getLogger(__name__)


@dataclass
class EnrichmentEvent:
    """Structured enrichment event."""

    timestamp: str
    span_hash: str
    file_path: str
    lines: tuple[int, int]
    success: bool
    duration_sec: float
    model: str
    chain: str | None = None
    backend: str | None = None
    attempts: int = 1
    tokens_in: int | None = None
    tokens_out: int | None = None
    tokens_per_second: float | None = None
    error: str | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        d = {
            "timestamp": self.timestamp,
            "span_hash": self.span_hash,
            "path": self.file_path,
            "lines": list(self.lines),
            "success": self.success,
            "duration_sec": round(self.duration_sec, 3),
            "model": self.model,
        }
        if self.chain:
            d["chain"] = self.chain
        if self.backend:
            d["backend"] = self.backend
        if self.attempts > 1:
            d["attempts"] = self.attempts
        if self.tokens_in is not None:
            d["tokens_in"] = self.tokens_in
        if self.tokens_out is not None:
            d["tokens_out"] = self.tokens_out
        if self.tokens_per_second is not None:
            d["tok_s"] = round(self.tokens_per_second, 1)
        if self.error:
            d["error"] = self.error[:200]  # Truncate long errors
        if self.correlation_id:
            d["request_id"] = self.correlation_id
        return d


class EnrichmentLogger:
    """Thread-safe, atomic JSONL logger for enrichment events.

    Features:
    - Atomic appends with file locking (fcntl)
    - JSON validation before write (no corrupt lines)
    - Separate log files for different event types

    Log Files:
    - run_ledger.jsonl: All enrichment events (success + failure)
    - enrichment_metrics.jsonl: Detailed performance metrics
    """

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self.log_dir / "run_ledger.jsonl"
        self._metrics_path = self.log_dir / "enrichment_metrics.jsonl"

    def log_success(
        self,
        span_hash: str,
        file_path: str,
        start_line: int,
        end_line: int,
        duration_sec: float,
        model: str,
        meta: dict[str, Any] | None = None,
        chain: str | None = None,
        attempts: int = 1,
        correlation_id: str | None = None,
    ) -> None:
        """Log a successful enrichment."""
        meta = meta or {}

        event = EnrichmentEvent(
            timestamp=datetime.now(UTC).isoformat(),
            span_hash=span_hash,
            file_path=file_path,
            lines=(start_line, end_line),
            success=True,
            duration_sec=duration_sec,
            model=model,
            chain=chain,
            backend=meta.get("backend"),
            attempts=attempts,
            tokens_in=meta.get("tokens_in") or meta.get("prompt_eval_count"),
            tokens_out=meta.get("tokens_out") or meta.get("eval_count"),
            tokens_per_second=meta.get("tokens_per_second"),
            correlation_id=correlation_id,
        )

        self._write_event(event)

    def log_failure(
        self,
        span_hash: str,
        file_path: str,
        start_line: int,
        end_line: int,
        duration_sec: float,
        error: str,
        model: str | None = None,
        attempts: int = 1,
        correlation_id: str | None = None,
    ) -> None:
        """Log a failed enrichment."""
        event = EnrichmentEvent(
            timestamp=datetime.now(UTC).isoformat(),
            span_hash=span_hash,
            file_path=file_path,
            lines=(start_line, end_line),
            success=False,
            duration_sec=duration_sec,
            model=model or "unknown",
            attempts=attempts,
            error=error,
            correlation_id=correlation_id,
        )

        self._write_event(event)

    def log_batch_summary(
        self,
        total: int,
        succeeded: int,
        failed: int,
        skipped: int,
        duration_sec: float,
        repo_root: str | None = None,
    ) -> None:
        """Log a batch enrichment summary."""
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "batch_summary",
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "duration_sec": round(duration_sec, 2),
            "success_rate": round(succeeded / total, 3) if total > 0 else 0,
        }
        if repo_root:
            event["repo_root"] = repo_root

        self._atomic_append(self._ledger_path, event)

    def _write_event(self, event: EnrichmentEvent) -> None:
        """Write an enrichment event to the ledger."""
        self._atomic_append(self._ledger_path, event.to_dict())

    def _atomic_append(self, path: Path, data: dict[str, Any]) -> None:
        """Append a JSON line atomically with file locking.

        Guarantees:
        1. Line is valid JSON (validated before write)
        2. Write is atomic (single write + flush)
        3. Multi-process safe (advisory lock)
        """
        try:
            # Build complete line in memory first
            line = json.dumps(data, separators=(",", ":")) + "\n"

            # Validate JSON structure (should never fail, but safety first)
            json.loads(line)

            with open(path, "a") as f:
                # Advisory lock for multi-process safety
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(line)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            # Never let logging failures crash enrichment
            _logger.warning("Failed to write enrichment log: %s", e)


def repair_ledger(log_path: Path) -> tuple[int, int]:
    """Repair a corrupt JSONL ledger file.

    Reads all lines, keeps valid JSON, discards corrupt lines.
    Original file is backed up to .bak before rewriting.

    Args:
        log_path: Path to the ledger file

    Returns:
        Tuple of (valid_lines_count, discarded_lines_count)
    """
    if not log_path.exists():
        return 0, 0

    valid_lines = []
    discarded = 0

    with open(log_path) as f:
        for line_num, raw_line in enumerate(f, 1):
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue
            try:
                json.loads(stripped_line)
                valid_lines.append(stripped_line)
            except json.JSONDecodeError as e:
                _logger.warning("Discarding corrupt line %d: %s", line_num, e)
                discarded += 1

    if discarded > 0:
        # Backup original
        backup_path = log_path.with_suffix(".log.bak")
        log_path.rename(backup_path)
        _logger.info("Backed up corrupt ledger to %s", backup_path)

        # Write repaired file
        with open(log_path, "w") as f:
            for line in valid_lines:
                f.write(line + "\n")

        _logger.info(
            "Repaired ledger: %d valid lines, %d discarded",
            len(valid_lines),
            discarded,
        )

    return len(valid_lines), discarded
