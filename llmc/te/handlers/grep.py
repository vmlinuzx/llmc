"""
Grep handler for Tool Envelope.

Wraps ripgrep (rg) with ranking, breadcrumbs, and progressive disclosure.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..config import get_output_budget, get_te_config
from ..formatter import FormattedOutput, TeMeta, compute_hot_zone, format_breadcrumb, format_meta_header
from ..sniffer import sniff
from ..store import store


@dataclass
class GrepMatch:
    """A single grep match with metadata."""

    path: str
    line_no: int
    content: str
    is_definition: bool = False
    is_test: bool = False
    content_type: str = "text"


@dataclass
class GrepResult:
    """Complete grep result."""

    matches: list[GrepMatch]
    total_count: int
    raw_output: str
    error: str | None = None


def _is_definition(content: str) -> bool:
    """Heuristic: is this line a definition?"""
    patterns = [
        r"^\s*(def|class|function|const|let|var|type|interface)\s+",
        r"^\s*\w+\s*[=:]\s*(function|async|class|\()",
        r"^\s*export\s+(default\s+)?(function|class|const|let|var)",
    ]
    return any(re.match(p, content) for p in patterns)


def _is_test_file(path: str) -> bool:
    """Is this a test file?"""
    return bool(re.search(r"(test_|_test\.|\.test\.|tests/|__tests__|spec\.)", path.lower()))


def _rank_match(match: GrepMatch) -> tuple[int, int]:
    """Sort key: (priority, line_no). Lower is better."""
    # Priority levels:
    # 0 = definition in non-test file (best)
    # 1 = non-test file match
    # 2 = definition in test file
    # 3 = test file match (least priority)
    if match.is_test:
        priority = 2 if match.is_definition else 3
    else:
        priority = 0 if match.is_definition else 1
    return (priority, match.line_no)


def _parse_rg_output(output: str) -> list[GrepMatch]:
    """Parse ripgrep output into matches."""
    matches = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        # rg format: path:line:content
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, line_no_str, content = parts
        try:
            line_no = int(line_no_str)
        except ValueError:
            continue

        match = GrepMatch(
            path=path,
            line_no=line_no,
            content=content,
            is_definition=_is_definition(content),
            is_test=_is_test_file(path),
            content_type=sniff(path),
        )
        matches.append(match)
    return matches


def _run_rg(
    pattern: str,
    path: str | None,
    workspace: Path,
    timeout_ms: int,
) -> GrepResult:
    """Run ripgrep and return parsed results."""
    cmd = ["rg", "--line-number", "--no-heading", "--color=never"]

    # Add pattern
    cmd.append(pattern)

    # Add path if specified, else workspace
    if path:
        target = Path(path)
        if not target.is_absolute():
            target = workspace / target
        cmd.append(str(target))
    else:
        cmd.append(str(workspace))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
            cwd=workspace,
        )
        output = result.stdout
        # rg returns 1 for no matches, 2 for errors
        if result.returncode == 2:
            return GrepResult(
                matches=[],
                total_count=0,
                raw_output="",
                error=result.stderr.strip() or "ripgrep error",
            )
        matches = _parse_rg_output(output)
        return GrepResult(
            matches=matches,
            total_count=len(matches),
            raw_output=output,
        )
    except subprocess.TimeoutExpired:
        return GrepResult(
            matches=[],
            total_count=0,
            raw_output="",
            error="timeout",
        )
    except FileNotFoundError:
        return GrepResult(
            matches=[],
            total_count=0,
            raw_output="",
            error="ripgrep_not_found",
        )
    except Exception as e:
        return GrepResult(
            matches=[],
            total_count=0,
            raw_output="",
            error=str(e),
        )


def handle_grep(
    pattern: str,
    path: str | None = None,
    raw: bool = False,
    agent_id: str | None = None,
    repo_root: Path | None = None,
) -> FormattedOutput:
    """
    Handle grep command with enrichment.

    Args:
        pattern: Regex pattern to search
        path: Optional path to search in
        raw: If True, bypass enrichment (return raw rg output)
        agent_id: Agent identifier for budget lookup
        repo_root: Repository root (auto-detected if None)

    Returns:
        FormattedOutput with MPD header and breadcrumbed content
    """
    cfg = get_te_config(repo_root)
    workspace = cfg.workspace_root

    # Run ripgrep
    result = _run_rg(pattern, path, workspace, cfg.grep_timeout_ms)

    # Error handling
    if result.error:
        meta = TeMeta(cmd="grep", error=result.error)
        return FormattedOutput(
            header=format_meta_header(meta),
            content=f"[TE] {result.error}",
        )

    # Raw bypass mode
    if raw:
        return FormattedOutput(
            header="",
            content=result.raw_output,
        )

    # Rank matches
    ranked = sorted(result.matches, key=_rank_match)

    # Make paths relative for hot zone computation
    workspace_str = str(workspace)

    def relative_dir(path: str) -> str:
        """Get relative directory path."""
        if path.startswith(workspace_str):
            path = path[len(workspace_str):].lstrip("/")
        if "/" in path:
            return path.rsplit("/", 1)[0]
        return "."

    # Compute hot zone with relative paths
    file_counts = Counter(relative_dir(m.path) for m in ranked)
    hot_zone = compute_hot_zone(dict(file_counts), result.total_count)

    # Apply output budget
    budget = get_output_budget(agent_id, repo_root)
    preview_count = cfg.grep_preview_matches

    # Build output with breadcrumbs
    output_lines = []
    breadcrumbs = []
    chars_used = 0
    matches_shown = 0
    truncated = False
    handle_id = None

    # Separate non-test and test matches
    non_test = [m for m in ranked if not m.is_test]
    test_only = [m for m in ranked if m.is_test]

    # Show non-test matches first
    for match in non_test[:preview_count]:
        # Use relative path for cleaner output
        display_path = match.path
        if display_path.startswith(workspace_str):
            display_path = display_path[len(workspace_str):].lstrip("/")
        line = f"{display_path}:{match.line_no}: {match.content}"
        if chars_used + len(line) > budget:
            truncated = True
            break
        output_lines.append(line)
        chars_used += len(line) + 1
        matches_shown += 1

    # Add breadcrumb if more non-test matches exist
    remaining_non_test = len(non_test) - matches_shown
    if remaining_non_test > 0:
        # Compute directory breakdown for remaining (using relative paths)
        remaining_dirs = Counter(
            relative_dir(m.path) for m in non_test[matches_shown:]
        )
        dir_summary = ", ".join(f"{d} ({c})" for d, c in remaining_dirs.most_common(3))
        breadcrumbs.append(format_breadcrumb(f"{remaining_non_test} more in: {dir_summary}"))
        truncated = True

    # Add test matches summary
    if test_only:
        breadcrumbs.append(format_breadcrumb(f"{len(test_only)} test file matches"))

    # Store full result if truncated
    if truncated:
        handle_id = store(result.raw_output, "grep", len(result.raw_output))

    # Build meta header
    meta = TeMeta(
        cmd="grep",
        matches=result.total_count,
        files=len(set(m.path for m in result.matches)),
        truncated=truncated if truncated else None,
        handle=handle_id,
        hot_zone=hot_zone,
    )

    return FormattedOutput(
        header=format_meta_header(meta),
        content="\n".join(output_lines),
        breadcrumbs=breadcrumbs,
    )
