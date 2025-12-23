from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
import logging
import os
from pathlib import Path
import time

from llmc.rag.routing import is_format_allowed, resolve_domain

# Import classification logic
from llmc.routing.content_type import classify_slice

from .config import (
    ensure_rag_storage,
    index_path_for_write,
    rag_dir,
    spans_export_path as resolve_spans_export_path,
)
from .database import Database
from .index_naming import resolve_index_name
from .lang import extract_spans, language_for_path
from .types import FileRecord, SpanRecord
from llmc.core import find_repo_root
from .utils import (
    _gitignore_matcher,
    git_changed_paths,
    git_commit_sha,
    iter_source_files,
)

# Import sidecar generator (optional dependency - for code documentation)
try:
    from .sidecar_generator import SidecarGenerator

    SIDECAR_AVAILABLE = True
except ImportError:
    SIDECAR_AVAILABLE = False

# Import document sidecar system (for PDF/DOCX conversion)
try:
    from .sidecar import (
        SidecarConverter,
        get_sidecar_path,
        is_sidecar_eligible,
        is_sidecar_stale,
        get_converter as get_doc_sidecar_converter,
    )

    DOC_SIDECAR_AVAILABLE = True
except ImportError:
    DOC_SIDECAR_AVAILABLE = False

log = logging.getLogger(__name__)

EMBED_META = "embed_meta.json"


class IndexStats(dict):
    @property
    def files(self) -> int:
        return self.get("files", 0)

    @property
    def spans(self) -> int:
        return self.get("spans", 0)

    @property
    def sidecars(self) -> int:
        return self.get("sidecars", 0)

    @property
    def unchanged(self) -> int:
        return self.get("unchanged", 0)


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


def populate_span_hashes(spans: list[SpanRecord], source: bytes, lang: str) -> None:
    for span in spans:
        span_bytes = source[span.byte_start : span.byte_end]
        h = hashlib.sha256()
        h.update(lang.encode("utf-8"))
        h.update(b"\0")
        h.update(span_bytes)
        span.span_hash = f"sha256:{h.hexdigest()}"


def build_file_record(
    file_path: Path, lang: str, repo_root: Path, source: bytes
) -> FileRecord:
    stat = (repo_root / file_path).stat()
    return FileRecord(
        path=file_path,
        lang=lang,
        file_hash=compute_hash(source),
        size=stat.st_size,
        mtime=stat.st_mtime,
    )


def generate_sidecar_if_enabled(
    file_path: Path, lang: str, source: bytes, repo_root: Path
) -> Path | None:
    """Generate .md sidecar file if enabled via environment variable.

    Args:
        file_path: Relative file path
        lang: Language name
        source: File content (bytes)
        repo_root: Repository root path

    Returns:
        Path to generated sidecar, or None if disabled/failed
    """
    # Check if sidecar generation is enabled
    if not SIDECAR_AVAILABLE:
        return None

    if os.environ.get("LLMC_GENERATE_SIDECARS", "1") == "0":
        return None

    try:
        generator = SidecarGenerator(lang)
        markdown = generator.generate_from_file(repo_root / file_path, content=source)

        # Write to .artifacts/ directory
        artifacts_dir = repo_root / ".artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        sidecar_path = artifacts_dir / f"{file_path.stem}.md"
        sidecar_path.write_text(markdown, encoding="utf-8")

        return sidecar_path
    except Exception as e:
        # Silently fail sidecar generation - don't break indexing
        log.warning("Failed to generate sidecar for %s: %s", file_path, e)
        return None


def generate_doc_sidecar_if_needed(
    file_path: Path, repo_root: Path
) -> tuple[Path | None, bytes | None]:
    """Generate markdown sidecar for documents (PDF, DOCX, etc.) if stale.
    
    Args:
        file_path: Relative file path
        repo_root: Repository root path
        
    Returns:
        Tuple of (sidecar_path, markdown_bytes) if generated, (None, None) otherwise
    """
    if not DOC_SIDECAR_AVAILABLE:
        return None, None
    
    if not is_sidecar_eligible(file_path):
        return None, None
    
    # Check if sidecar generation is disabled
    if os.environ.get("LLMC_DOC_SIDECARS", "1") == "0":
        return None, None
    
    # Skip if sidecar is fresh
    if not is_sidecar_stale(file_path, repo_root):
        # Sidecar exists and is fresh, just read it
        sidecar_path = get_sidecar_path(file_path, repo_root)
        try:
            import gzip
            with gzip.open(sidecar_path, "rt", encoding="utf-8") as f:
                content = f.read()
            return sidecar_path, content.encode("utf-8")
        except Exception:
            pass  # Fall through to regenerate
    
    # Generate new sidecar
    try:
        converter = get_doc_sidecar_converter()
        sidecar_path = converter.convert(file_path, repo_root)
        if sidecar_path:
            content = converter.read_sidecar(sidecar_path)
            if content:
                return sidecar_path, content.encode("utf-8")
    except Exception as e:
        log.warning(f"Failed to generate doc sidecar for {file_path}: {e}")
    
    return None, None


def cleanup_doc_sidecar(file_path: Path, repo_root: Path) -> bool:
    """Remove orphaned document sidecar when source file is deleted.
    
    Args:
        file_path: Relative path of deleted source file
        repo_root: Repository root path
        
    Returns:
        True if sidecar was deleted, False otherwise
    """
    if not DOC_SIDECAR_AVAILABLE:
        return False
    
    if not is_sidecar_eligible(file_path):
        return False
    
    sidecar_path = get_sidecar_path(file_path, repo_root)
    if sidecar_path.exists():
        try:
            sidecar_path.unlink()
            log.info(f"Removed orphan sidecar: {sidecar_path}")
            
            # Try to remove empty parent directories
            try:
                sidecar_path.parent.rmdir()
            except OSError:
                pass  # Directory not empty
            
            return True
        except Exception as e:
            log.warning(f"Failed to remove orphan sidecar {sidecar_path}: {e}")
    
    return False

def index_repo(
    include_paths: Iterable[Path] | None = None,
    since: str | None = None,
    export_json: bool = True,
    show_domain_decisions: bool = False,
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

    counts = {
        "files": 0,
        "spans": 0,
        "skipped": 0,
        "unchanged": 0,
        "sidecars": 0,
        "duration_sec": 0.0,
    }
    start_time = time.time()

    try:
        for relative_path in files_iter:
            absolute_path = repo_root / relative_path

            # Gating check (Phase 1: block HL7/CCDA)
            domain, reason_type, reason_detail = resolve_domain(
                relative_path, repo_root
            )
            if not is_format_allowed(domain, absolute_path, repo_root):
                counts["skipped"] += 1
                if show_domain_decisions:
                    print(
                        f"INFO indexer: file={relative_path} domain={domain} action=SKIP reason=gated_format"
                    )
                continue

            lang = language_for_path(relative_path)
            if not lang:
                # Check if this is a document that can be converted to a sidecar
                doc_sidecar_path, doc_content = generate_doc_sidecar_if_needed(
                    relative_path, repo_root
                )
                if doc_sidecar_path and doc_content:
                    # Use the sidecar markdown content instead
                    lang = "markdown"
                    source = doc_content
                    counts["sidecars"] += 1
                    log.info(f"Generated document sidecar: {relative_path} -> {doc_sidecar_path}")
                else:
                    counts["skipped"] += 1
                    continue
            else:
                source = absolute_path.read_bytes()

            # INCREMENTAL INDEXING: Skip files with unchanged content
            new_hash = compute_hash(source)
            existing_hash = db.get_file_hash(relative_path)
            if existing_hash == new_hash:
                # MIGRATION FIX: Force re-extraction for markdown files with 0 spans
                # This handles upgrade from pre-TechDocsExtractor versions where markdown
                # files were indexed but no spans were extracted.
                if lang == "markdown":
                    span_count = db.conn.execute(
                        """
                        SELECT COUNT(*) FROM spans s
                        JOIN files f ON s.file_id = f.id
                        WHERE f.path = ?
                        """,
                        (str(relative_path),),
                    ).fetchone()[0]
                    if span_count == 0:
                        log.info(f"Migration: re-extracting {relative_path} (0 spans from old indexer)")
                        # Fall through to extraction instead of skipping
                    else:
                        counts["unchanged"] += 1
                        continue
                else:
                    counts["unchanged"] += 1
                    continue

            # ATOMIC OPERATION: Extract spans and generate sidecar from same source/AST
            file_process_start = time.time()
            text_preview = source[:1024].decode("utf-8", errors="ignore")
            classification = classify_slice(relative_path, None, text_preview)

            spans = extract_spans(relative_path, lang, source)
            for span in spans:
                span.slice_type = classification.slice_type
                span.slice_language = classification.slice_language
                span.classifier_confidence = classification.confidence
                span.classifier_version = classification.classifier_version

            populate_span_hashes(spans, source, lang)
            file_record = build_file_record(relative_path, lang, repo_root, source)

            # Domain logging
            index_name = resolve_index_name(f"emb_{domain}", repo_root.name, "per-repo")

            if show_domain_decisions:
                reason_str = (
                    f"{reason_type}:{reason_detail}" if reason_detail else reason_type
                )
                print(
                    f"INFO indexer: file={relative_path} domain={domain} reason={reason_str}"
                )

            file_ms = int((time.time() - file_process_start) * 1000)
            log.info(
                f"domain={domain} "
                f'override="{reason_detail if reason_detail else reason_type}" '
                f'index="{index_name}" '
                f'extractor="TreeSitter" '
                f"chunks={len(spans)} "
                f"ms={file_ms}"
            )

            # Generate sidecar (using same loaded content)
            sidecar_path = generate_sidecar_if_enabled(
                relative_path, lang, source, repo_root
            )
            if sidecar_path:
                counts["sidecars"] += 1

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

    counts = {
        "files": 0,
        "spans": 0,
        "deleted": 0,
        "unchanged": 0,
        "sidecars": 0,
        "duration_sec": 0.0,
    }
    start_time = time.time()
    try:
        for rel in paths:
            absolute = repo_root / rel
            if not absolute.exists():
                with db.transaction():
                    db.delete_file(rel)
                # Clean up any associated document sidecar
                cleanup_doc_sidecar(rel, repo_root)
                counts["deleted"] += 1
                continue
            # Respect ignore rules (gitignore + .ragignore + LLMC_RAG_EXCLUDE)
            if matcher(rel):
                with db.transaction():
                    db.delete_file(rel)
                counts["deleted"] += 1
                continue

            # Gating check
            domain, _, _ = resolve_domain(rel, repo_root)
            if not is_format_allowed(domain, absolute, repo_root):
                counts["deleted"] += 1  # Effectively treated as not indexed
                # Ensure it is removed from DB if it was there
                with db.transaction():
                    db.delete_file(rel)
                continue

            lang = language_for_path(rel)
            if not lang:
                # Check if this is a document that can be converted to a sidecar
                doc_sidecar_path, doc_content = generate_doc_sidecar_if_needed(
                    rel, repo_root
                )
                if doc_sidecar_path and doc_content:
                    # Use the sidecar markdown content instead
                    lang = "markdown"
                    source = doc_content
                    counts["sidecars"] += 1
                    log.info(f"Generated document sidecar: {rel} -> {doc_sidecar_path}")
                else:
                    counts["deleted"] += 1
                    with db.transaction():
                        db.delete_file(rel)
                    continue
            else:
                source = absolute.read_bytes()

            # INCREMENTAL INDEXING: Skip files with unchanged content
            new_hash = compute_hash(source)
            existing_hash = db.get_file_hash(rel)
            if existing_hash == new_hash:
                # MIGRATION FIX: Force re-extraction for markdown files with 0 spans
                if lang == "markdown":
                    span_count = db.conn.execute(
                        """
                        SELECT COUNT(*) FROM spans s
                        JOIN files f ON s.file_id = f.id
                        WHERE f.path = ?
                        """,
                        (str(rel),),
                    ).fetchone()[0]
                    if span_count == 0:
                        log.info(f"Migration: re-extracting {rel} (0 spans from old indexer)")
                        # Fall through to extraction
                    else:
                        counts["unchanged"] += 1
                        continue
                else:
                    counts["unchanged"] += 1
                    continue

            # ATOMIC OPERATION: Extract spans and generate sidecar
            text_preview = source[:1024].decode("utf-8", errors="ignore")
            classification = classify_slice(rel, None, text_preview)

            spans = extract_spans(rel, lang, source)
            for span in spans:
                span.slice_type = classification.slice_type
                span.slice_language = classification.slice_language
                span.classifier_confidence = classification.confidence
                span.classifier_version = classification.classifier_version

            populate_span_hashes(spans, source, lang)
            file_record = build_file_record(rel, lang, repo_root, source)

            # Generate sidecar (using same loaded content)
            sidecar_path = generate_sidecar_if_enabled(rel, lang, source, repo_root)
            if sidecar_path:
                counts["sidecars"] += 1

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
