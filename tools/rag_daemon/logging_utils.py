"""Logging helpers for the LLMC RAG Daemon."""

from __future__ import annotations

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

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)
    logger.addHandler(ch)

    # File handler
    log_file = Path(config.log_path) / "rag-daemon.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(level)
    logger.addHandler(fh)

    logger.propagate = False
    return logger
