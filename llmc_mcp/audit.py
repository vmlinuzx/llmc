"""Audit trail module for LLMC MCP."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger("llmc-mcp.audit")


class TokenAuditWriter:
    """CSV writer for token audit trail.

    Appends per-request token usage to CSV file for cost tracking.
    Thread-safe with lazy file creation.

    CRITICAL: This class must NEVER raise exceptions that kill tool calls.
    All file operations are wrapped in try/except to fail silently.
    """

    CSV_HEADERS = [
        "timestamp",
        "correlation_id",
        "tool",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "success",
    ]

    def __init__(self, csv_path: str | Path, enabled: bool = True):
        self.csv_path = Path(csv_path)
        self.enabled = enabled
        self._lock = Lock()
        self._initialized = False
        self._failed = False  # Track if initialization failed to avoid repeated warnings

    def _ensure_file(self) -> None:
        """Create CSV file with headers if needed. Fails silently on error."""
        if self._initialized or self._failed:
            return

        try:
            # Create parent dirs
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)

            # Write headers if file doesn't exist
            if not self.csv_path.exists():
                with open(self.csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)

            self._initialized = True
        except Exception as e:
            # CRITICAL: Never let audit failures kill tool calls
            self._failed = True
            logger.warning(
                f"Failed to initialize audit CSV at {self.csv_path}: {e}. "
                "Token audit will be disabled. This is not critical."
            )

    def record(
        self,
        correlation_id: str,
        tool: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Append a record to the audit CSV. Fails silently on error."""
        if not self.enabled or self._failed:
            return

        try:
            with self._lock:
                self._ensure_file()

                if self._failed:  # Check again after ensure_file
                    return

                with open(self.csv_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                            correlation_id,
                            tool,
                            tokens_in,
                            tokens_out,
                            round(latency_ms, 2),
                            "ok" if success else "error",
                        ]
                    )
        except Exception as e:
            # CRITICAL: Never let audit failures kill tool calls
            logger.warning(f"Failed to write audit record: {e}. Continuing without audit.")
            self._failed = True  # Disable further attempts
