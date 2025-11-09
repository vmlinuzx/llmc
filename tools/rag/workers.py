from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from jsonschema import Draft7Validator, ValidationError

from .config import (
    embedding_model_dim,
    embedding_model_name,
    embedding_normalize,
)
from .database import Database
from .utils import _gitignore_matcher
from .embeddings import HASH_MODELS, build_embedding_backend

MAX_SNIPPET_CHARS = 800


def _snippet(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


ENRICHMENT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "summary_120w",
        "inputs",
        "outputs",
        "side_effects",
        "pitfalls",
        "usage_snippet",
        "evidence",
    ],
    "properties": {
        "summary_120w": {"type": "string", "maxLength": 1200},
        "inputs": {"type": "array", "items": {"type": "string"}},
        "outputs": {"type": "array", "items": {"type": "string"}},
        "side_effects": {"type": "array", "items": {"type": "string"}},
        "pitfalls": {"type": "array", "items": {"type": "string"}},
        "usage_snippet": {"type": ["string", "null"], "maxLength": 1200},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["field", "lines"],
                "properties": {
                    "field": {"type": "string"},
                    "lines": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "additionalProperties": False,
            },
        },
        "model": {"type": ["string", "null"]},
        "schema_version": {"type": ["string", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

ENRICHMENT_VALIDATOR = Draft7Validator(ENRICHMENT_SCHEMA)


def enrichment_plan(db: Database, repo_root: Path, limit: int = 10, cooldown_seconds: int = 0) -> List[dict]:
    """Build an enrichment plan, skipping spans touched within the cooldown window."""
    items = db.pending_enrichments(limit=limit, cooldown_seconds=cooldown_seconds)
    matcher = _gitignore_matcher(repo_root)
    plan: List[dict] = []
    for item in items:
        # Respect ignores (gitignore + .ragignore + LLMC_RAG_EXCLUDE)
        try:
            rel_path = item.file_path
            if matcher(rel_path):
                # silently skip ignored paths
                continue
        except Exception:
            # defensive: never block enrichment on ignore checks
            pass
        try:
            code = item.read_source(repo_root)
        except FileNotFoundError:
            # Source file vanished (e.g., moved or deleted) – drop related spans so the plan stays healthy.
            with db.transaction():
                db.delete_file(item.file_path)
            print(
                f"[enrichment_plan] skipped missing file {item.file_path}",
                file=sys.stderr,
            )
            continue
        plan.append(
            {
                "span_hash": item.span_hash,
                "path": str(item.file_path),
                "lang": item.lang,
                "lines": [item.start_line, item.end_line],
                "code_snippet": _snippet(code),
                "llm_contract": {
                    "schema_version": "enrichment.v1",
                    "fields": ["summary_120w", "inputs", "outputs", "side_effects", "pitfalls", "usage_snippet", "evidence"],
                    "word_caps": {"summary_120w": 120, "usage_snippet": 12},
                    "instructions": "Return ONLY valid JSON per schema. Cite exact line ranges for every claim. If unsure, use null.",
                },
            }
        )
    return plan


def embedding_plan(
    db: Database,
    repo_root: Path,
    limit: int = 10,
    model: str | None = None,
    dim: int | None = None,
) -> List[dict]:
    resolved_model = model or embedding_model_name()
    if resolved_model in HASH_MODELS:
        resolved_dim = dim or 64
    else:
        resolved_dim = dim or embedding_model_dim()
    normalize = False if resolved_model in HASH_MODELS else embedding_normalize()

    items = db.pending_embeddings(limit=limit)
    plan: List[dict] = []
    for item in items:
        code = item.read_source(repo_root)
        plan.append(
            {
                "span_hash": item.span_hash,
                "path": str(item.file_path),
                "lang": item.lang,
                "lines": [item.start_line, item.end_line],
                "code_length": len(code),
                "embedding_hint": {
                    "model": resolved_model,
                    "dim": resolved_dim,
                    "normalize": normalize,
                    "truncate_after": 1024,
                },
            }
        )
    return plan


def _format_embedding_text(item, code: str) -> str:
    header = f"{item.file_path} • {item.lang} • lines {item.start_line}-{item.end_line}"
    body = code.strip()
    if not body:
        return header
    return f"{header}\n\n{body}"


def execute_embeddings(
    db: Database,
    repo_root: Path,
    limit: int = 10,
    model: str | None = None,
    dim: int | None = None,
) -> Tuple[List[Tuple[str, int]], str, int]:
    items = db.pending_embeddings(limit=limit)
    if not items:
        fallback_model = model or embedding_model_name()
        if model and model in HASH_MODELS:
            fallback_dim = dim or 64
        else:
            fallback_dim = dim or embedding_model_dim()
        return [], fallback_model, fallback_dim

    backend = build_embedding_backend(model, dim=dim)

    prepared_hashes: List[str] = []
    texts: List[str] = []
    for item in items:
        try:
            code = item.read_source(repo_root)
        except FileNotFoundError:
            continue
        formatted = _format_embedding_text(item, code)
        if not formatted.strip():
            continue
        texts.append(formatted)
        prepared_hashes.append(item.span_hash)

    if not texts:
        return [], backend.model_name, backend.dim

    vectors = backend.embed_passages(texts)
    if len(vectors) != len(prepared_hashes):  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"Embedding backend returned {len(vectors)} vectors for {len(prepared_hashes)} spans"
        )
    created: List[Tuple[str, int]] = []
    with db.transaction():
        db.ensure_embedding_meta(backend.model_name, backend.dim)
        for span_hash, vector in zip(prepared_hashes, vectors):
            db.store_embedding(span_hash, vector)
            created.append((span_hash, backend.dim))
    return created, backend.model_name, backend.dim


def default_enrichment_callable(model: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _call(prompt: Dict[str, Any]) -> Dict[str, Any]:
        path = prompt.get("path", "")
        start, end = prompt.get("lines", [0, 0])
        code: str = prompt.get("code", "")
        lines = code.splitlines()
        snippet = "\n".join(lines[:12]) if lines else None
        summary = f"{path}:{start}-{end} auto-summary generated offline."
        return {
            "summary_120w": summary,
            "inputs": [],
            "outputs": [],
            "side_effects": [],
            "pitfalls": [],
            "usage_snippet": snippet,
            "evidence": [{"field": "summary_120w", "lines": [start, end]}],
            "model": model,
            "schema_version": "enrichment.v1",
            "tags": [],
        }

    return _call


def execute_enrichment(
    db: Database,
    repo_root: Path,
    llm_call: Callable[[Dict[str, Any]], Dict[str, Any]],
    limit: int = 10,
    model: str = "local-qwen",
    cooldown_seconds: int = 0,
) -> Tuple[int, List[str]]:
    """Run enrichment over pending spans.

    Args:
        db: Database connection.
        repo_root: Repository root path.
        llm_call: Callable taking (prompt_dict) -> dict (LLM response).
        limit: Max spans to process.
        model: Model identifier recorded in the DB.
        cooldown_seconds: Skip spans whose source files changed within this window.

    Returns:
        (success_count, error_messages)
    """

    items = db.pending_enrichments(limit=limit, cooldown_seconds=cooldown_seconds)
    if not items:
        return 0, []

    successes = 0
    errors: List[str] = []

    with db.transaction():
        for item in items:
            code = item.read_source(repo_root)
            prompt = {
                "span_hash": item.span_hash,
                "path": str(item.file_path),
                "lang": item.lang,
                "lines": [item.start_line, item.end_line],
                "code": code,
                "instructions": "Return ONLY valid JSON per schema. Cite exact line ranges for every claim. If unsure, use null.",
            }
            try:
                response = llm_call(prompt)
            except Exception as exc:  # pragma: no cover - depends on user llm callable
                errors.append(f"{item.span_hash}: LLM call failed - {exc}")
                continue

            ok, validation_errors = validate_enrichment(response, item.start_line, item.end_line)
            if not ok:
                errors.append(
                    f"{item.span_hash}: validation failed - {', '.join(validation_errors) or 'unknown error'}"
                )
                continue

            payload = {
                **response,
                "model": model,
                "schema_version": response.get("schema_version", "enrichment.v1"),
            }
            db.store_enrichment(item.span_hash, payload)
            successes += 1

    return successes, errors
def _within_range(lines: List[int], start: int, end: int) -> bool:
    if len(lines) != 2:
        return False
    a, b = lines
    return start <= a <= end and start <= b <= end


def validate_enrichment(payload: Dict[str, Any], span_start: int, span_end: int) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        ENRICHMENT_VALIDATOR.validate(payload)
    except ValidationError as exc:
        errors.append(f"schema: {exc.message}")
        return False, errors

    for entry in payload.get("evidence", []):
        if not _within_range(entry.get("lines", []), span_start, span_end):
            errors.append(f"evidence lines out of range: {entry}")

    summary = payload.get("summary_120w", "") or ""
    if len(summary.split()) > 120:
        errors.append("summary_120w exceeds 120 words")

    snippet = payload.get("usage_snippet")
    if snippet is not None and len(snippet.splitlines()) > 12:
        errors.append("usage_snippet exceeds 12 lines")

    return len(errors) == 0, errors
