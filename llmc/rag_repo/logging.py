from __future__ import annotations

import logging


class PathSafetyWarning(Warning):
    """Warning category for path-safety-driven skips."""


def warn_skip(entry: str, reason: str) -> None:
    """Emit a standardized warning when a path or entry is skipped for safety."""
    logging.getLogger("llmc.paths").warning("skip %s: %s", entry, reason)
