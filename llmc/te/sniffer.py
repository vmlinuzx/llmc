"""
Content-type sniffer for Tool Envelope.

50-line classifier: extension map + log regex + JSON heuristic.
Falls back to "text" gracefully.
"""

from __future__ import annotations

import re
from pathlib import Path

EXTENSION_MAP = {
    ".py": "code/python",
    ".js": "code/javascript",
    ".ts": "code/typescript",
    ".jsx": "code/javascript",
    ".tsx": "code/typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".log": "log",
    ".csv": "tabular",
    ".tsv": "tabular",
    ".sql": "code/sql",
    ".sh": "code/shell",
    ".bash": "code/shell",
    ".rs": "code/rust",
    ".go": "code/go",
    ".rb": "code/ruby",
    ".java": "code/java",
    ".c": "code/c",
    ".h": "code/c",
    ".cpp": "code/cpp",
    ".hpp": "code/cpp",
}

LOG_PATTERN = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}|"  # ISO date
    r"^\[?(ERROR|WARN|INFO|DEBUG)\]?|"  # Log level
    r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}"  # Syslog date
)


def sniff(path: str, sample: str | None = None) -> str:
    """Detect content type from path extension or content sample."""
    ext = Path(path).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    if sample:
        lines = sample.split("\n")[:5]
        if sum(1 for line in lines if LOG_PATTERN.match(line)) >= 2:
            return "log"
        stripped = sample.strip()
        if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
            return "json"
    return "text"
