from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from jsonschema import Draft7Validator, ValidationError

from .database import Database

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
    plan: List[dict] = []
    for item in items:
        code = item.read_source(repo_root)
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


def embedding_plan(db: Database, repo_root: Path, limit: int = 10, model: str = "hash-emb-v1", dim: int = 64) -> List[dict]:
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
                    "model": model,
                    "dim": dim,
                    "normalize": True,
                    "truncate_after": 1024,
                },
            }
        )
    return plan


def _deterministic_embedding(payload: bytes, dim: int) -> List[float]:
    """Hash-based embedding placeholder to keep the worker deterministic/offline."""
    values: List[float] = []
    seed = payload
    while len(values) < dim:
        digest = hashlib.sha256(seed).digest()
        seed = digest  # next round
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                continue
            val = struct.unpack("<I", chunk)[0]
            # map integer to [-1, 1]
            values.append((val / 0xFFFFFFFF) * 2 - 1)
            if len(values) == dim:
                break
    return values


def execute_embeddings(db: Database, repo_root: Path, limit: int = 10, model: str = "hash-emb-v1", dim: int = 64) -> List[Tuple[str, int]]:
    items = db.pending_embeddings(limit=limit)
    if not items:
        return []
    created: List[Tuple[str, int]] = []
    with db.transaction():
        db.ensure_embedding_meta(model, dim)
        for item in items:
            payload = item.read_bytes(repo_root)
            vector = _deterministic_embedding(payload, dim=dim)
            db.store_embedding(item.span_hash, vector)
            created.append((item.span_hash, dim))
    return created


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
