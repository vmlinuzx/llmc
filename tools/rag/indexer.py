from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Iterable, List, Optional

from .database import Database
from .config import (
    ensure_rag_storage,
    index_path_for_write,
    rag_dir,
    spans_export_path as resolve_spans_export_path,
)
from .lang import extract_spans, language_for_path
from .types import FileRecord, SpanRecord
from .utils import find_repo_root, git_changed_paths, git_commit_sha, iter_source_files, _gitignore_matcher

EMBED_META = "embed_meta.json"


class IndexStats(dict):
    @property
    def files(self) -> int:
        return self.get("files", 0)

    @property
    def spans(self) -> int:
        return self.get("spans", 0)


def repo_paths(repo_root: Path) -> Path:
    return rag_dir(repo_root)


def db_path(repo_root: Path) -> Path:
    return index_path_for_write(repo_root)


def spans_export_path(repo_root: Path) -> Path:
    return resolve_spans_export_path(repo_root)


def ensure_storage(repo_root: Path) -> None:
    ensure_rag_storage(repo_root)


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def populate_span_hashes(spans: List[SpanRecord], source: bytes, lang: str) -> None:
    for span in spans:
        span_bytes = source[span.byte_start : span.byte_end]
        h = hashlib.sha256()
        h.update(lang.encode("utf-8"))
        h.update(b"\0")
        h.update(span_bytes)
        span.span_hash = f"sha256:{h.hexdigest()}"


def build_file_record(file_path: Path, lang: str, repo_root: Path, source: bytes) -> FileRecord:
    stat = (repo_root / file_path).stat()
    return FileRecord(
        path=file_path,
        lang=lang,
        file_hash=compute_hash(source),
        size=stat.st_size,
        mtime=stat.st_mtime,
    )


def index_repo(
    include_paths: Optional[Iterable[Path]] = None,
    since: Optional[str] = None,
    export_json: bool = True,
) -> IndexStats:
    repo_root = find_repo_root()
    ensure_storage(repo_root)

    if since:
        include_paths = git_changed_paths(repo_root, since)

    files_iter = iter_source_files(repo_root, include_paths)

    db = Database(db_path(repo_root))
    repo_id = repo_root.name
    commit_sha = git_commit_sha(repo_root) or "unknown"

    spans_export_file = None
    if export_json:
        spans_export_file = spans_export_path(repo_root)
        spans_export_file.parent.mkdir(parents=True, exist_ok=True)
        spans_export_handle = spans_export_file.open("w", encoding="utf-8")
    else:
        spans_export_handle = None

    counts = {"files": 0, "spans": 0, "skipped": 0, "duration_sec": 0.0}
    start_time = time.time()

    try:
        for relative_path in files_iter:
            absolute_path = repo_root / relative_path
            lang = language_for_path(relative_path)
            if not lang:
                counts["skipped"] += 1
                continue
            source = absolute_path.read_bytes()
            spans = extract_spans(relative_path, lang, source)
            populate_span_hashes(spans, source, lang)
            file_record = build_file_record(relative_path, lang, repo_root, source)

            with db.transaction():
                file_id = db.upsert_file(file_record)
                db.replace_spans(file_id, spans)

            if spans_export_handle is not None:
                for span in spans:
                    record = span.to_json(repo_id=repo_id, commit_sha=commit_sha)
                    spans_export_handle.write(json.dumps(record) + "\n")

            counts["files"] += 1
            counts["spans"] += len(spans)
    finally:
        if spans_export_handle is not None:
            spans_export_handle.close()
        db.close()

    counts["duration_sec"] = round(time.time() - start_time, 3)
    return IndexStats(counts)


def sync_paths(paths: Iterable[Path]) -> IndexStats:
    repo_root = find_repo_root()
    ensure_storage(repo_root)
    db = Database(db_path(repo_root))
    repo_id = repo_root.name
    commit_sha = git_commit_sha(repo_root) or "unknown"
    spans_export_handle = spans_export_path(repo_root).open("a", encoding="utf-8")
    matcher = _gitignore_matcher(repo_root)

    counts = {"files": 0, "spans": 0, "deleted": 0, "duration_sec": 0.0}
    start_time = time.time()
    try:
        for rel in paths:
            absolute = repo_root / rel
            if not absolute.exists():
                with db.transaction():
                    db.delete_file(rel)
                counts["deleted"] += 1
                continue
            # Respect ignore rules (gitignore + .ragignore + LLMC_RAG_EXCLUDE)
            if matcher(rel):
                with db.transaction():
                    db.delete_file(rel)
                counts["deleted"] += 1
                continue
            lang = language_for_path(rel)
            if not lang:
                counts["deleted"] += 1
                with db.transaction():
                    db.delete_file(rel)
                continue
            source = absolute.read_bytes()
            spans = extract_spans(rel, lang, source)
            populate_span_hashes(spans, source, lang)
            file_record = build_file_record(rel, lang, repo_root, source)
            with db.transaction():
                file_id = db.upsert_file(file_record)
                db.replace_spans(file_id, spans)
            for span in spans:
                record = span.to_json(repo_id=repo_id, commit_sha=commit_sha)
                spans_export_handle.write(json.dumps(record) + "\n")
            counts["files"] += 1
            counts["spans"] += len(spans)
    finally:
        spans_export_handle.close()
        db.close()
    counts["duration_sec"] = round(time.time() - start_time, 3)
    return IndexStats(counts)
