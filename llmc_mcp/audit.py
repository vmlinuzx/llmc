"""Audit trail module for LLMC MCP."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class TokenAuditWriter:
    """CSV writer for token audit trail.
    
    Appends per-request token usage to CSV file for cost tracking.
    Thread-safe with lazy file creation.
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
    
    def _ensure_file(self) -> None:
        """Create CSV file with headers if needed."""
        if self._initialized:
            return
        
        # Create parent dirs
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write headers if file doesn't exist
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
        
        self._initialized = True
    
    def record(
        self,
        correlation_id: str,
        tool: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Append a record to the audit CSV."""
        if not self.enabled:
            return
        
        with self._lock:
            self._ensure_file()
            
            with open(self.csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    correlation_id,
                    tool,
                    tokens_in,
                    tokens_out,
                    round(latency_ms, 2),
                    "ok" if success else "error",
                ])
