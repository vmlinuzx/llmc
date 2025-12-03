"""
Formatter for Tool Envelope.

Builds MPD (Minimal Progressive Disclosure) meta headers and streaming breadcrumbs.
The response stream IS the teaching. No hand-holding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


@dataclass
class TeMeta:
    """MPD meta header fields."""

    v: int = 1  # Schema version
    cmd: str = ""  # Subcommand name

    # Result magnitude (command-specific)
    matches: int | None = None  # grep
    lines: int | None = None  # cat
    files: int | None = None  # find
    size: int | None = None  # bytes

    # Optional fields
    truncated: bool | None = None
    handle: str | None = None
    hot_zone: str | None = None  # Where results concentrate
    content_type: str | None = None
    error: str | None = None

    # FORBIDDEN: next_moves, suggestions, hints arrays
    # One exception: hint for capabilities LLM cannot infer from training
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        d = {"v": self.v, "cmd": self.cmd}
        for key in [
            "matches",
            "lines",
            "files",
            "size",
            "truncated",
            "handle",
            "hot_zone",
            "content_type",
            "error",
            "hint",
        ]:
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        return d


def format_meta_header(meta: TeMeta) -> str:
    """Format MPD meta header between markers."""
    return "# TE_BEGIN_META\n" + json.dumps(meta.to_dict(), ensure_ascii=False) + "\n# TE_END_META"


def format_breadcrumb(message: str) -> str:
    """Format a streaming breadcrumb."""
    return f"\n# TE: {message}"


@dataclass
class FormattedOutput:
    """Complete formatted output with header and content."""

    header: str
    content: str
    breadcrumbs: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render the complete output."""
        parts = [self.header, "", self.content]
        if self.breadcrumbs:
            parts.extend(self.breadcrumbs)
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        # Parse header JSON to get meta dict
        meta = {}
        if self.header.startswith("# TE_BEGIN_META"):
            try:
                # Extract JSON between markers
                lines = self.header.splitlines()
                if len(lines) >= 2:
                    meta = json.loads(lines[1])
            except Exception:
                pass

        return {"meta": meta, "content": self.content, "breadcrumbs": self.breadcrumbs}


def compute_hot_zone(file_counts: dict[str, int], total: int) -> str | None:
    """Compute hot zone string if results concentrate in one area."""
    if not file_counts or total < 5:
        return None

    # Group by directory
    dir_counts: dict[str, int] = {}
    for path, count in file_counts.items():
        parts = path.split("/")
        if len(parts) > 1:
            # Use first two path components as zone
            zone = "/".join(parts[:2]) + "/"
        else:
            zone = parts[0]
        dir_counts[zone] = dir_counts.get(zone, 0) + count

    # Find dominant zone (>50% of results)
    for zone, count in sorted(dir_counts.items(), key=lambda x: -x[1]):
        pct = count * 100 // total
        if pct >= 50:
            return f"{zone} ({pct}%)"

    return None
