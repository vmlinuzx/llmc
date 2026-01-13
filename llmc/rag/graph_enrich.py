from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


def _is_truthy(val: object) -> bool:
    """Return True for common truthy string values."""
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y"}


def discover_enrichment_db(repo_root: Path) -> Path | None:
    """
    Discover an enrichment database for the given repo root.

    Order:
      1) $LLMC_ENRICH_DB (if it exists)
      2) <repo_root>/.rag/index_v2.db
      3) <repo_root>/.rag/index.db
      4) <repo_root>/.rag/enrich.db
    """
    env = os.getenv("LLMC_ENRICH_DB")
    if env:
        path = Path(env).expanduser()
        if path.exists():
            return path
    rag_root = Path(repo_root) / ".rag"
    for name in ("index_v2.db", "index.db", "enrich.db"):
        candidate = rag_root / name
        if candidate.exists():
            return candidate
    return None


def compute_span_hash(
    file: str,
    start: int,
    end: int,
    *,
    text: str | None = None,
    with_text: bool = False,
) -> str:
    """
    Compute a stable hash for a (file, start, end, [text]) triple.

    Hash algorithm is controlled by LLMC_ENRICH_HASH_ALGO: sha1 (default), blake2, md5.
    """
    algo = os.getenv("LLMC_ENRICH_HASH_ALGO", "sha1").lower()
    parts = [str(Path(file).as_posix()).lower(), str(int(start)), str(int(end))]
    if with_text and text:
        norm = " ".join(str(text).split())
        parts.append(norm)
    key = "|".join(parts).encode("utf-8", errors="ignore")
    if algo == "blake2":
        return hashlib.blake2b(key, digest_size=20).hexdigest()
    if algo == "md5":
        return hashlib.md5(key, usedforsecurity=False).hexdigest()
    return hashlib.sha1(key, usedforsecurity=False).hexdigest()


class GraphEnrichmentDB:
    """
    Minimal read-only helper around the enrichment database for graph merge.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._has_span_hash: bool | None = None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _probe(self) -> None:
        """Populate _has_span_hash by introspecting the enrichments table."""
        if self._has_span_hash is not None:
            return
        self._has_span_hash = False
        try:
            with self._connect() as con:
                cur = con.cursor()
                cur.execute("PRAGMA table_info(enrichments)")
                cols = [str(row[1]).lower() for row in cur.fetchall()]
                if "span_hash" in cols:
                    self._has_span_hash = True
        except Exception:
            self._has_span_hash = False

    def find_for_span(
        self,
        file: str,
        start: int,
        end: int,
        *,
        text: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """
        Look up enrichment for a given span.

        Returns (payload_dict, strategy) where strategy is one of:
        "span(no_text)", "span(with_text)", "line", "path", "error", or "none".
        """
        if not self.db_path.exists():
            return None, "none"
        try:
            self._probe()
        except Exception:
            # Schema detection is best-effort.
            pass
        try:
            with self._connect() as con:
                cur = con.cursor()

                # 1) span_hash without text (primary join for graphs).
                if self._has_span_hash:
                    h = compute_span_hash(file, start, end, text=None, with_text=False)
                    cur.execute(
                        "SELECT summary, inputs, outputs, pitfalls, evidence "
                        "FROM enrichments WHERE span_hash = ? LIMIT 1",
                        (h,),
                    )
                    row = cur.fetchone()
                    if row:
                        return _row_to_dict(row), "span(no_text)"

                # 2) span_hash with text when available.
                if self._has_span_hash and text:
                    h = compute_span_hash(file, start, end, text=text, with_text=True)
                    cur.execute(
                        "SELECT summary, inputs, outputs, pitfalls, evidence "
                        "FROM enrichments WHERE span_hash = ? LIMIT 1",
                        (h,),
                    )
                    row = cur.fetchone()
                    if row:
                        return _row_to_dict(row), "span(with_text)"

                # 3) (path, line) exact using start line.
                cur.execute(
                    "SELECT summary, inputs, outputs, pitfalls, evidence "
                    "FROM enrichments WHERE path = ? AND line = ? LIMIT 1",
                    (file, int(start)),
                )
                row = cur.fetchone()
                if row:
                    return _row_to_dict(row), "line"

                # 4) path-only fallback.
                cur.execute(
                    "SELECT summary, inputs, outputs, pitfalls, evidence "
                    "FROM enrichments WHERE path = ? LIMIT 1",
                    (file,),
                )
                row = cur.fetchone()
                if row:
                    return _row_to_dict(row), "path"
        except Exception:
            return None, "error"
        return None, "none"


def _row_to_dict(row: tuple) -> dict[str, Any]:
    keys = ["summary", "inputs", "outputs", "pitfalls", "evidence"]
    out: dict[str, Any] = {}
    for key, value in zip(keys, row, strict=False):
        if value is not None:
            out[key] = value
    return out


def _entity_path_and_span(entity: Any) -> tuple[str | None, int | None, int | None]:
    """
    Best-effort extraction of (path, start, end) for a graph entity.
    """
    path = getattr(entity, "file_path", None) or getattr(entity, "path", None)
    start = getattr(entity, "start_line", None)
    end = getattr(entity, "end_line", None)
    if path is None:
        loc = getattr(entity, "location", None)
        if loc is not None:
            path = getattr(loc, "path", None)
            start = start or getattr(loc, "start_line", None)
            end = end or getattr(loc, "end_line", None)
    return path, start, end


def _normalize_repo_relative(repo_root: Path, path: str) -> str:
    """
    Normalize an input path to a repo-relative POSIX path for DB joins.
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            return p.as_posix()
        rel = p.resolve().relative_to(repo_root.resolve())
        return rel.as_posix()
    except Exception:
        return Path(path).name


def _merge_into_metadata(
    entity: Any,
    payload: dict[str, Any],
    *,
    strategy: str,
    db_path: Path,
    span_hash: str | None,
) -> None:
    """
    Merge enrichment payload into entity.metadata with traceability.
    """
    metadata = getattr(entity, "metadata", None)
    if metadata is None:
        try:
            entity.metadata = {}
            metadata = entity.metadata
        except Exception:
            return
    if not isinstance(metadata, dict):
        return

    enrichment = metadata.setdefault("enrichment", {})
    for key, value in payload.items():
        enrichment.setdefault(key, value)

    meta = metadata.setdefault("__enrich_meta", {})
    meta["strategy"] = strategy
    meta["db"] = str(db_path)
    if span_hash is not None:
        meta["span_hash"] = span_hash


def enrich_graph_entities(
    graph: Any, repo_root: Path, *, max_per_entity: int = 1
) -> Any:
    """
    Merge enrichment snippets from the DB into graph entities.

    The function is fail-soft:
    - Respects LLMC_ENRICH (default on).
    - No-ops when DB is missing or unreadable.
    - Never raises; returns the original graph object.
    """
    if not _is_truthy(os.getenv("LLMC_ENRICH", "on")):
        return graph

    db_path = discover_enrichment_db(repo_root)
    if not db_path:
        return graph

    try:
        db = GraphEnrichmentDB(db_path)
    except Exception:
        return graph

    entities = getattr(graph, "entities", None) or getattr(graph, "nodes", None)
    if not entities:
        return graph

    for entity in entities:
        try:
            file_path, start, end = _entity_path_and_span(entity)
            if not file_path or start is None or end is None:
                continue
            rel = _normalize_repo_relative(repo_root, file_path)
            payload, strategy = db.find_for_span(rel, int(start), int(end), text=None)
            if not payload:
                continue
            span_hash: str | None = None
            if strategy.startswith("span"):
                with_text = strategy.endswith("(with_text)")
                span_hash = compute_span_hash(
                    rel,
                    int(start),
                    int(end),
                    text=None if not with_text else "",
                    with_text=with_text,
                )
            _merge_into_metadata(
                entity, payload, strategy=strategy, db_path=db_path, span_hash=span_hash
            )
        except Exception:
            continue
    return graph


def enrich_graph_file(graph_json_path: Path, repo_root: Path) -> None:
    """
    Post-process an existing graph JSON on disk and merge enrichment.

    This is a convenience for callers that already emitted a graph and want
    to retrofit enrichment into the entity metadata without changing their
    build pipeline.
    """
    data = json.loads(Path(graph_json_path).read_text(encoding="utf-8"))
    entities = data.get("entities") or data.get("nodes")
    if not entities:
        return

    class _EntityWrapper:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.__dict__.update(payload)

    graph = type(
        "GraphWrapper", (object,), {"entities": [_EntityWrapper(d) for d in entities]}
    )()
    enrich_graph_entities(graph, repo_root)

    for idx, entity in enumerate(graph.entities):
        entities[idx].update(getattr(entity, "__dict__", {}))

    Path(graph_json_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
