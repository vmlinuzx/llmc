"""Logging helpers for the LLMC RAG Daemon."""

from __future__ import annotations

from datetime import UTC
import logging
from pathlib import Path

from .models import DaemonConfig


def get_logger(name: str, config: DaemonConfig) -> logging.Logger:
    """Configure and return a logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Console handler (Text)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)
    logger.addHandler(ch)

    # File handler (JSONL)
    log_file = Path(config.log_path) / "rag-daemon.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(JSONFormatter())
    fh.setLevel(level)
    logger.addHandler(fh)

    logger.propagate = False
    return logger


class JSONFormatter(logging.Formatter):
    """Simple JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime
        import json

        # format message first to handle args
        message = record.getMessage()

        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": message,
            "path": record.pathname,
            "line": record.lineno,
        }

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry)
