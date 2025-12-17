from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileRecord:
    path: Path
    lang: str
    file_hash: str
    size: int
    mtime: float


@dataclass
class SpanRecord:
    file_path: Path
    lang: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    byte_start: int
    byte_end: int
    span_hash: str
    doc_hint: str | None = None
    imports: list[str] = field(default_factory=list)
    # Content routing metadata
    slice_type: str = "other"
    slice_language: str | None = None
    classifier_confidence: float = 0.0
    classifier_version: str = ""

    def read_bytes(self, repo_root: Path) -> bytes:
        data = (repo_root / self.file_path).read_bytes()
        return data[self.byte_start : self.byte_end]

    def read_source(self, repo_root: Path) -> str:
        return self.read_bytes(repo_root).decode("utf-8", errors="replace")

    def to_json(self, repo_id: str, commit_sha: str) -> dict:
        return {
            "repo_id": repo_id,
            "commit_sha": commit_sha,
            "path": str(self.file_path),
            "lang": self.lang,
            "symbol": self.symbol,
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "span_hash": self.span_hash,
            "imports": self.imports,
            "doc_hint": self.doc_hint,
            "slice_type": self.slice_type,
            "slice_language": self.slice_language,
            "classifier_confidence": self.classifier_confidence,
            "classifier_version": self.classifier_version,
        }


@dataclass
class SpanWorkItem:
    span_hash: str
    file_path: Path
    lang: str
    start_line: int
    end_line: int
    byte_start: int
    byte_end: int
    slice_type: str = "other"
    slice_language: str | None = None
    classifier_confidence: float = 0.0

    def read_bytes(self, repo_root: Path) -> bytes:
        data = (repo_root / self.file_path).read_bytes()
        return data[self.byte_start : self.byte_end]

    def read_source(self, repo_root: Path) -> str:
        return self.read_bytes(repo_root).decode("utf-8", errors="replace")


@dataclass
class EnrichmentRecord:
    """Lightweight projection of an enrichment row joined with its span symbol.

    This is intentionally minimal and storage-agnostic so it can be used
    by the schema graph builder, search adapters, and tests without
    depending on SQLite row objects.
    """

    span_hash: str
    symbol: str
    summary: str | None
    evidence: str | None
    inputs: str | None
    outputs: str | None
    side_effects: str | None
    pitfalls: str | None
    usage_snippet: str | None
    tags: str | None = None
    model: str | None = None
    created_at: str | None = None
    schema_ver: str | None = None
    # Content routing metadata
    content_type: str | None = None
    content_language: str | None = None
    content_type_confidence: float | None = None
    content_type_source: str | None = None
