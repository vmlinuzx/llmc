"""
SQLite-backed enrichment attachment helpers for RAG Nav results.

This module provides a tiny, defensive, read-only store that looks up
pre-computed enrichment snippets by `(path, line)` and attaches them to
search / where-used / lineage results.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any

from llmc.rag_nav.models import LineageResult, SearchResult, WhereUsedResult  # type: ignore

log = logging.getLogger("llmc.enrich")


@dataclass
class EnrichmentSnippet:
    """Single enrichment snippet associated with a source location."""

    summary: str | None = None
    inputs: str | None = None
    outputs: str | None = None
    pitfalls: str | None = None
    content_type: str | None = None
    content_language: str | None = None


class SqliteEnrichmentStore:
    """
    Tiny read-only store with schema awareness and span-hash join.

    The database is expected to expose an `enrichments` table with:
      (path TEXT, line INTEGER, summary TEXT, inputs TEXT, outputs TEXT, pitfalls TEXT)
    and may optionally include a `span_hash` column to support direct joins.

    Any database or schema errors are treated as empty results.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._has_span_hash: bool | None = None

    def _connect(self) -> sqlite3.Connection:
        """
        Open a SQLite connection to the underlying database.

        URI mode is not used; this operates on a simple file path.
        """
        return sqlite3.connect(str(self.db_path))

    def _check_schema(self) -> None:
        """Populate `_has_span_hash` by introspecting the enrichments table."""
        if self._has_span_hash is not None:
            return
        self._has_span_hash = False
        try:
            with self._connect() as con:
                cur = con.cursor()
                cur.execute("PRAGMA table_info(enrichments)")
                cols = [str(r[1]).lower() for r in cur.fetchall()]
                if "span_hash" in cols:
                    self._has_span_hash = True
        except Exception:
            self._has_span_hash = False

    def snippets_for(
        self, path: str, line: int | None = None, limit: int = 1
    ) -> list[EnrichmentSnippet]:
        """
        Look up enrichment snippets for the given path and optional line.

        When `line` is provided, this first attempts an exact (path, line) match.
        If no rows are returned, it falls back to path-only lookups.
        Any database or I/O errors are treated as empty results.
        """
        if not self.db_path.exists():
            return []
        try:
            limit_int = max(1, int(limit))
        except Exception:
            limit_int = 1

        q_line = "SELECT summary, inputs, outputs, pitfalls, content_type, content_language FROM enrichments WHERE path = ? AND line = ? LIMIT ?"
        q_path = "SELECT summary, inputs, outputs, pitfalls, content_type, content_language FROM enrichments WHERE path = ? LIMIT ?"

        rows: list[tuple] = []
        try:
            with self._connect() as con:
                cur = con.cursor()
                if line is not None:
                    try:
                        cur.execute(q_line, (path, int(line), limit_int))
                        rows = cur.fetchall()
                    except Exception:
                        rows = []
                if not rows:
                    cur.execute(q_path, (path, limit_int))
                    rows = cur.fetchall()
        except Exception:
            return []

        snippets: list[EnrichmentSnippet] = []
        for row in rows:
            # Coerce non-string columns to None for safety.
            values: list[str | None] = []
            for value in row:
                values.append(value if isinstance(value, str) else None)
            snippets.append(EnrichmentSnippet(*values))
        return snippets

    def _compute_span_hash(
        self,
        file: str | None,
        start: int | None,
        end: int | None,
        text: str | None,
    ) -> str | None:
        """Compute a span hash compatible with the core enrichment DB."""
        if file is None or start is None or end is None:
            return None
        algo = os.getenv("LLMC_ENRICH_HASH_ALGO", "sha1").lower()
        with_text = str(os.getenv("LLMC_ENRICH_HASH_WITH_TEXT", "1")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        key_parts = [str(Path(file).as_posix()).lower(), str(int(start)), str(int(end))]
        if with_text and text:
            norm = " ".join(str(text).split())
            key_parts.append(norm)
        key = "|".join(key_parts).encode("utf-8", errors="ignore")
        if algo == "blake2":
            return hashlib.blake2b(key, digest_size=20).hexdigest()
        if algo == "md5":
            return hashlib.md5(key, usedforsecurity=False).hexdigest()
        return hashlib.sha1(key, usedforsecurity=False).hexdigest()

    def snippets_for_span_or_path(
        self,
        file: str | None,
        start: int | None,
        end: int | None,
        text: str | None,
        limit: int = 1,
    ) -> tuple[list[EnrichmentSnippet], str]:
        """
        Lookup using span_hash (if available) → (path, line) → path.

        Returns a pair of (snippets, strategy) where strategy is one of:
        "span", "line", "path", "error", or "none".
        """
        if not self.db_path.exists():
            return [], "none"
        try:
            self._check_schema()
        except Exception:
            # Schema detection is best-effort.
            pass

        try:
            with self._connect() as con:
                cur = con.cursor()
                # 1) span_hash, when supported and we can compute it.
                if self._has_span_hash:
                    h = self._compute_span_hash(file, start, end, text)
                    if h:
                        cur.execute(
                            "SELECT summary, inputs, outputs, pitfalls, content_type, content_language FROM enrichments WHERE span_hash = ? LIMIT ?",
                            (h, int(limit)),
                        )
                        rows = cur.fetchall()
                        if rows:
                            snippets = [
                                EnrichmentSnippet(
                                    *[
                                        (val if isinstance(val, str) else None)
                                        for val in row
                                    ]
                                )
                                for row in rows
                            ]
                            return snippets, "span"

                # 2) (path, line) exact lookup.
                if file is not None and start is not None:
                    cur.execute(
                        "SELECT summary, inputs, outputs, pitfalls, content_type, content_language FROM enrichments WHERE path = ? AND line = ? LIMIT ?",
                        (file, int(start), int(limit)),
                    )
                    rows = cur.fetchall()
                    if rows:
                        snippets = [
                            EnrichmentSnippet(
                                *[
                                    (val if isinstance(val, str) else None)
                                    for val in row
                                ]
                            )
                            for row in rows
                        ]
                        return snippets, "line"

                # 3) Path-only fallback.
                if file is not None:
                    cur.execute(
                        "SELECT summary, inputs, outputs, pitfalls, content_type, content_language FROM enrichments WHERE path = ? LIMIT ?",
                        (file, int(limit)),
                    )
                    rows = cur.fetchall()
                    if rows:
                        snippets = [
                            EnrichmentSnippet(
                                *[
                                    (val if isinstance(val, str) else None)
                                    for val in row
                                ]
                            )
                            for row in rows
                        ]
                        return snippets, "path"
        except Exception:
            return [], "error"
        return [], "none"


@dataclass
class EnrichStats:
    """Lightweight counters for enrichment attachment behavior."""

    db_open_fail: int = 0
    path_matches: int = 0
    line_matches: int = 0
    snippets_attached: int = 0
    fields_truncated: int = 0
    span_matches: int = 0


def _trim_fields(
    d: dict[str, Any], max_chars: int | None, stats: EnrichStats | None
) -> dict[str, Any]:
    """
    Trim string fields in `d` to at most `max_chars`, updating `stats`.
    """
    if not max_chars or max_chars <= 0:
        return d
    out: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, str) and len(value) > max_chars:
            out[key] = value[: max_chars - 1] + "…"
            if stats is not None:
                stats.fields_truncated += 1
        else:
            out[key] = value
    return out


def _item_path_and_line(item: object) -> tuple[str | None, int | None]:
    """
    Best-effort extraction of (path, line) from an item with optional snippet/location.
    """
    path: str | None = getattr(item, "file", None) or getattr(item, "path", None)
    line: int | None = getattr(item, "line", None) or getattr(item, "start_line", None)

    snippet = getattr(item, "snippet", None)
    location = getattr(snippet, "location", None)
    if location is not None:
        if path is None:
            path = getattr(location, "path", None)
        if line is None:
            line = getattr(location, "start_line", None)

    try:
        line_int = int(line) if line is not None else None
    except Exception:
        line_int = None
    return path, line_int


def _attach_to_items(
    items: Iterable[object],
    store: SqliteEnrichmentStore,
    max_snippets: int,
    *,
    max_chars: int | None,
    stats: EnrichStats | None,
) -> None:
    try:
        max_snippets_int = max(1, int(max_snippets))
    except Exception:
        max_snippets_int = 1

    for item in items:
        try:
            path, line = _item_path_and_line(item)
            if not path:
                continue
            snippets = store.snippets_for(path, line, limit=max_snippets_int)
            if not snippets:
                continue
            data = {k: v for k, v in asdict(snippets[0]).items() if v is not None}
            data = _trim_fields(data, max_chars, stats)
            if not data:
                continue
            item.enrichment = data  # type: ignore[attr-defined]
            if stats is not None:
                stats.snippets_attached += 1
                if line is not None:
                    stats.line_matches += 1
                else:
                    stats.path_matches += 1
        except Exception:
            # Fail-soft: never let enrichment attachment break core behavior.
            continue


def attach_enrichments_to_search_result(
    result: SearchResult,
    store: SqliteEnrichmentStore,
    max_snippets: int = 1,
    *,
    max_chars: int | None = None,
    stats: EnrichStats | None = None,
) -> SearchResult:
    """
    Attach at most one enrichment snippet to each search hit in-place.

    This mutates `result` by setting `hit.enrichment` to a compact dictionary
    per hit that has at least one enrichment snippet. Missing databases, query
    errors, or unexpected hit shapes are treated as no-ops.
    """
    items: Iterable[object] | None = getattr(result, "items", None)
    if not items:
        return result

    try:
        max_snippets_int = max(1, int(max_snippets))
    except Exception:
        max_snippets_int = 1

    for hit in items:
        try:
            path, line = _item_path_and_line(hit)
            snippet = getattr(hit, "snippet", None)
            location = getattr(snippet, "location", None)
            start = (
                getattr(location, "start_line", None) if location is not None else line
            )
            end = getattr(location, "end_line", None) if location is not None else line
            text = getattr(snippet, "text", None)

            snippets, strategy = store.snippets_for_span_or_path(
                path, start, end, text, limit=max_snippets_int
            )
            if not snippets:
                continue

            data = {k: v for k, v in asdict(snippets[0]).items() if v is not None}
            data = _trim_fields(data, max_chars, stats)
            if not data:
                continue

            hit.enrichment = data  # type: ignore[attr-defined]
            if stats is not None:
                stats.snippets_attached += 1
                if strategy == "span":
                    stats.span_matches += 1
                elif strategy == "line":
                    stats.line_matches += 1
                elif strategy == "path":
                    stats.path_matches += 1
        except Exception:
            # Fail-soft: never let enrichment attachment break core behavior.
            continue
    return result


def attach_enrichments_to_where_used(
    result: WhereUsedResult,
    store: SqliteEnrichmentStore,
    max_snippets: int = 1,
    *,
    max_chars: int | None = None,
    stats: EnrichStats | None = None,
) -> WhereUsedResult:
    """
    Attach enrichment snippets to where-used result items in-place.
    """
    items: Iterable[object] | None = getattr(result, "items", None)
    if not items:
        return result

    try:
        max_snippets_int = max(1, int(max_snippets))
    except Exception:
        max_snippets_int = 1

    for item in items:
        try:
            path, line = _item_path_and_line(item)
            snippet = getattr(item, "snippet", None)
            location = getattr(snippet, "location", None)
            start = (
                getattr(location, "start_line", None) if location is not None else line
            )
            end = getattr(location, "end_line", None) if location is not None else line
            text = getattr(snippet, "text", None)

            snippets, strategy = store.snippets_for_span_or_path(
                path, start, end, text, limit=max_snippets_int
            )
            if not snippets:
                continue

            data = {k: v for k, v in asdict(snippets[0]).items() if v is not None}
            data = _trim_fields(data, max_chars, stats)
            if not data:
                continue

            item.enrichment = data  # type: ignore[attr-defined]
            if stats is not None:
                stats.snippets_attached += 1
                if strategy == "span":
                    stats.span_matches += 1
                elif strategy == "line":
                    stats.line_matches += 1
                elif strategy == "path":
                    stats.path_matches += 1
        except Exception:
            continue
    return result


def attach_enrichments_to_lineage(
    result: LineageResult,
    store: SqliteEnrichmentStore,
    max_snippets: int = 1,
    *,
    max_chars: int | None = None,
    stats: EnrichStats | None = None,
) -> LineageResult:
    """
    Attach enrichment snippets to lineage result items in-place.
    """
    items: Iterable[object] | None = getattr(result, "items", None)
    if not items:
        return result

    try:
        max_snippets_int = max(1, int(max_snippets))
    except Exception:
        max_snippets_int = 1

    for item in items:
        try:
            path, line = _item_path_and_line(item)
            snippet = getattr(item, "snippet", None)
            location = getattr(snippet, "location", None)
            start = (
                getattr(location, "start_line", None) if location is not None else line
            )
            end = getattr(location, "end_line", None) if location is not None else line
            text = getattr(snippet, "text", None)

            snippets, strategy = store.snippets_for_span_or_path(
                path, start, end, text, limit=max_snippets_int
            )
            if not snippets:
                continue

            data = {k: v for k, v in asdict(snippets[0]).items() if v is not None}
            data = _trim_fields(data, max_chars, stats)
            if not data:
                continue

            item.enrichment = data  # type: ignore[attr-defined]
            if stats is not None:
                stats.snippets_attached += 1
                if strategy == "span":
                    stats.span_matches += 1
                elif strategy == "line":
                    stats.line_matches += 1
                elif strategy == "path":
                    stats.path_matches += 1
        except Exception:
            continue
    return result


def discover_enrichment_db(
    repo_root: Path | None, items: list[Any] | None
) -> Path | None:
    """
    Discover a plausible enrichment DB path based on repo_root or search items.
    """
    try:
        if repo_root:
            candidate = Path(repo_root) / ".rag" / "index_v2.db"
            if candidate.exists():
                return candidate
        if items:
            first = items[0]
            f = Path(getattr(first, "file", "") or "")
            for p in [f] + list(f.parents):
                candidate = p / ".rag" / "index_v2.db"
                if candidate.exists():
                    return candidate
    except Exception:
        return None
    return None
