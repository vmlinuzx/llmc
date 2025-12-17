"""
M5 Phase-1b: TE wrappers for repo + rag

Adds two thin tools that call the TE CLI through `te_run`:
- repo_read(root: str, path: str, max_bytes: Optional[int])
- rag_query(query: str, k: int = 5, index: Optional[str] = None, filters: Optional[dict] = None)

Both return the normalized envelope from `te_run`:
{"data": <json or {"raw": "..."}>, "meta": {...}}
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from typing import Any

from .te import te_run

try:
    from llmc_mcp.context import McpSessionContext  # provided by your codebase
except Exception:
    McpSessionContext = None  # type: ignore

logger = logging.getLogger(__name__)


def repo_read(
    root: str,
    path: str,
    *,
    max_bytes: int | None = None,
    ctx: McpSessionContext | None = None,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Read a file from a repo via TE.
    TE CLI is expected to support: te repo read --root ROOT --path PATH [--max-bytes N]
    """
    args = ["repo", "read", "--root", root, "--path", path]
    if isinstance(max_bytes, int) and max_bytes > 0:
        args += ["--max-bytes", str(max_bytes)]
    return te_run(args, ctx=ctx, cwd=root, allowed_roots=allowed_roots)


def rag_query(
    query: str,
    *,
    k: int = 5,
    index: str | None = None,
    filters: Mapping[str, Any] | None = None,
    ctx: McpSessionContext | None = None,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run a RAG query via TE.
    TE CLI is expected to support: te rag query --q QUERY [--k K] [--index NAME] [--filters JSON]
    """
    args = ["rag", "query", "--q", query]
    if isinstance(k, int) and k > 0:
        args += ["--k", str(k)]
    if index:
        args += ["--index", index]
    if filters:
        try:
            args += ["--filters", json.dumps(filters)]
        except Exception:
            logger.warning("Could not JSON-encode filters; ignoring.")
    return te_run(args, ctx=ctx, allowed_roots=allowed_roots)
