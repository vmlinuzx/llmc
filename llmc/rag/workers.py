from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft7Validator, ValidationError

from .config import (
    ConfigError,
    embedding_model_dim,
    embedding_model_name,
    embedding_normalize,
    get_route_for_slice_type,  # Added import
    load_config,
    resolve_route,  # Added import
)
from .database import Database
from .embeddings import HASH_MODELS, build_embedding_backend
from .utils import _gitignore_matcher

log = logging.getLogger(__name__)  # Initialize logger

MAX_SNIPPET_CHARS = 800


def _snippet(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


ENRICHMENT_SCHEMA: dict[str, Any] = {
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


def enrichment_plan(
    db: Database, repo_root: Path, limit: int = 10, cooldown_seconds: int = 0
) -> list[dict]:
    """Build an enrichment plan, skipping spans touched within the cooldown window."""
    items = db.pending_enrichments(limit=limit, cooldown_seconds=cooldown_seconds)
    matcher = _gitignore_matcher(repo_root)
    plan: list[dict] = []
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
                "content_type": item.slice_type,  # Add slice_type for routing
                "llm_contract": {
                    "schema_version": "enrichment.v1",
                    "fields": [
                        "summary_120w",
                        "inputs",
                        "outputs",
                        "side_effects",
                        "pitfalls",
                        "usage_snippet",
                        "evidence",
                    ],
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
) -> list[dict]:
    config = load_config(repo_root)
    # routes = config.get("embeddings", {}).get("routes", {})
    # slice_map = config.get("routing", {}).get("slice_type_to_route", {})
    profiles = config.get("embeddings", {}).get("profiles", {})

    items = db.pending_embeddings(limit=limit)
    plan: list[dict] = []
    for item in items:
        # Resolve routing
        route_name = get_route_for_slice_type(item.slice_type, repo_root)
        try:
            profile_name, index_name = resolve_route(route_name, "ingest", repo_root)
        except ConfigError as e:
            log.warning(f"Skipping span {item.span_hash} due to config error: {e}")
            continue

        log.debug(
            f"Embed Plan: Span {item.span_hash} (slice_type={item.slice_type}) "
            f"routed to: route='{route_name}', profile='{profile_name}', index='{index_name}'"
        )

        # Resolve model/dim from the resolved profile
        profile_cfg = profiles.get(profile_name, {})

        resolved_model = model
        if not resolved_model or resolved_model == "auto":
            resolved_model = profile_cfg.get("model") or embedding_model_name()

        resolved_dim = dim
        if not resolved_dim or resolved_dim <= 0:
            if resolved_model in HASH_MODELS:
                resolved_dim = 64
            else:
                resolved_dim = profile_cfg.get("dim") or embedding_model_dim()

        normalize = False if resolved_model in HASH_MODELS else embedding_normalize()

        code = item.read_source(repo_root)
        plan.append(
            {
                "span_hash": item.span_hash,
                "path": str(item.file_path),
                "lang": item.lang,
                "slice_type": item.slice_type,
                "route": route_name,
                "target_index": index_name,
                "lines": [item.start_line, item.end_line],
                "code_length": len(code),
                "embedding_hint": {
                    "model": resolved_model,
                    "dim": resolved_dim,
                    "normalize": normalize,
                    "truncate_after": 1024,
                    "profile": profile_name,
                },
            }
        )
    return plan


def _format_embedding_text(item, code: str, max_chars: int = 4000) -> str:
    """Format span for embedding, truncating to avoid Ollama batch overflow."""
    header = f"{item.file_path} • {item.lang} • lines {item.start_line}-{item.end_line}"
    body = code.strip()
    if not body:
        return header
    # Truncate to ~1000 tokens (4000 chars) to stay under Ollama's batch limit
    # This prevents "caching disabled but unable to fit entire input in a batch" panics
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... (truncated for embedding)"
    return f"{header}\n\n{body}"


def execute_embeddings(
    db: Database,
    repo_root: Path,
    limit: int = 10,
    model: str | None = None,
    dim: int | None = None,
) -> tuple[list[tuple[str, int]], str, int]:
    items = db.pending_embeddings(limit=limit)
    if not items:
        fallback_model = model or embedding_model_name()
        if model and model in HASH_MODELS:
            fallback_dim = dim or 64
        else:
            fallback_dim = dim or embedding_model_dim()
        return [], fallback_model, fallback_dim

    config = load_config(repo_root)

    # Group items by (profile_name, index_name, route_name)
    from collections import defaultdict

    groups = defaultdict(list)

    for item in items:
        route_name = get_route_for_slice_type(item.slice_type, repo_root)
        try:
            profile_name, index_name = resolve_route(route_name, "ingest", repo_root)
        except ConfigError as e:
            log.warning(f"Skipping span {item.span_hash} due to config error: {e}")
            continue

        groups[(profile_name, index_name, route_name)].append(item)

    total_created: list[tuple[str, int]] = []
    last_model = "mixed"
    last_dim = 0

    for (profile_name, index_name, route_name), group_items in groups.items():
        log.debug(
            f"Execute Embeddings: Processing {len(group_items)} spans for "
            f"route='{route_name}', profile='{profile_name}', index='{index_name}'"
        )

        profile_cfg = config.get("embeddings", {}).get("profiles", {})
        profile_details = profile_cfg.get(
            profile_name, {}
        )  # Get details for the resolved profile

        # Resolve model/dim (CLI overrides apply to all)
        resolved_model = model
        if not resolved_model or resolved_model == "auto":
            resolved_model = (
                profile_details.get("model") or embedding_model_name()
            )  # Use profile_details

        resolved_dim = dim
        if not resolved_dim or resolved_dim <= 0:
            if resolved_model in HASH_MODELS:
                resolved_dim = 64
            else:
                resolved_dim = (
                    profile_details.get("dim") or embedding_model_dim()
                )  # Use profile_details

        backend = build_embedding_backend(resolved_model, dim=resolved_dim)

        prepared_hashes: list[str] = []
        texts: list[str] = []
        for item in group_items:
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
            continue

        vectors = backend.embed_passages(texts)
        if len(vectors) != len(prepared_hashes):  # pragma: no cover - defensive guard
            raise RuntimeError(
                f"Embedding backend returned {len(vectors)} vectors for {len(prepared_hashes)} spans"
            )

        with db.transaction():
            db.ensure_embedding_meta(
                backend.model_name, backend.dim, profile=profile_name
            )
            for span_hash, vector in zip(prepared_hashes, vectors, strict=False):
                db.store_embedding(
                    span_hash,
                    vector,
                    route_name=route_name,
                    profile_name=profile_name,
                    table_name=index_name,
                )
                total_created.append((span_hash, backend.dim))

        last_model = backend.model_name
        last_dim = backend.dim

    return total_created, last_model, last_dim


def default_enrichment_callable(
    model: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _call(prompt: dict[str, Any]) -> dict[str, Any]:
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


def _is_latin1_safe(text: str) -> bool:
    """Return True if text contains only Latin-1 characters."""
    try:
        text.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def execute_enrichment(
    db: Database,
    repo_root: Path,
    llm_call: Callable[[dict[str, Any]], dict[str, Any]],
    limit: int = 10,
    model: str = "local-qwen",
    cooldown_seconds: int = 0,
    enforce_latin1: bool = False,
    *,
    code_first: bool | None = None,
    starvation_ratio_high: int | None = None,
    starvation_ratio_low: int | None = None,
) -> tuple[int, list[str]]:
    """Run enrichment over pending spans.

    Args:
        db: Database connection.
        repo_root: Repository root path.
        llm_call: Callable taking (prompt_dict) -> dict (LLM response).
        limit: Max spans to process.
        model: Model identifier recorded in the DB.
        cooldown_seconds: Skip spans whose source files changed within this window.
        enforce_latin1: If True, reject enrichments with non-Latin-1 characters.

    Returns:
        (success_count, error_messages)
    """

    items = db.pending_enrichments(limit=limit, cooldown_seconds=cooldown_seconds)
    if not items:
        return 0, []

    # Optional code-first scheduling using path weights.
    effective_code_first = False
    high_ratio = starvation_ratio_high if starvation_ratio_high is not None else 5
    low_ratio = starvation_ratio_low if starvation_ratio_low is not None else 1

    if high_ratio <= 0:
        high_ratio = 5
    if low_ratio <= 0:
        low_ratio = 1

    try:
        # Import lazily to avoid hard dependency when llmc is not available.
        from llmc.core import load_config as _load_llmc_config  # type: ignore[import]
        from llmc.enrichment import (  # type: ignore[import]
            FileClassifier,
            load_path_weight_map,
        )
    except Exception:  # pragma: no cover - defensive for non-LLMC environments
        _load_llmc_config = None  # type: ignore[assignment]
        FileClassifier = None  # type: ignore
        load_path_weight_map = None  # type: ignore[assignment]

    if code_first is not None:
        effective_code_first = bool(code_first)
    elif _load_llmc_config is not None:
        try:
            cfg = _load_llmc_config(repo_root)
            runner_cfg = (cfg.get("enrichment") or {}).get("runner") or {}
            effective_code_first = bool(runner_cfg.get("code_first_default", False))
            if starvation_ratio_high is None:
                high_ratio = int(runner_cfg.get("starvation_ratio_high", high_ratio))
            if starvation_ratio_low is None:
                low_ratio = int(runner_cfg.get("starvation_ratio_low", low_ratio))
        except Exception:
            effective_code_first = False

    scheduled_items = items
    if (
        effective_code_first
        and FileClassifier is not None
        and load_path_weight_map is not None
    ):
        try:
            cfg = _load_llmc_config(repo_root) if _load_llmc_config is not None else {}
            weight_map = load_path_weight_map(cfg)
            classifier = FileClassifier(repo_root=repo_root, weight_config=weight_map)

            decisions: list[tuple[Any, Any]] = []
            for item in items:
                decision = classifier.classify_span(item)
                decisions.append((item, decision))

            high_items: list[tuple[Any, Any]] = []
            mid_items: list[tuple[Any, Any]] = []
            low_items: list[tuple[Any, Any]] = []
            for item, decision in decisions:
                if decision.weight <= 3:
                    high_items.append((item, decision))
                elif decision.weight <= 6:
                    mid_items.append((item, decision))
                else:
                    low_items.append((item, decision))

            def key(pair):
                return pair[1].final_priority  # type: ignore[assignment]

            high_items.sort(key=key, reverse=True)
            mid_items.sort(key=key, reverse=True)
            low_items.sort(key=key, reverse=True)

            # Treat mid-tier as part of the high-priority pool for scheduling.
            high_pool = high_items + mid_items
            scheduled: list[Any] = []

            while high_pool or low_items:
                # Drain up to high_ratio items from high_pool.
                for _ in range(high_ratio):
                    if not high_pool:
                        break
                    item_dec = high_pool.pop(0)
                    scheduled.append(item_dec[0])
                    if len(scheduled) >= len(items):
                        break
                if len(scheduled) >= len(items):
                    break

                # Insert one low-priority item to avoid starvation.
                if low_items and low_ratio > 0:
                    low_item = low_items.pop(0)
                    scheduled.append(low_item[0])
                    if len(scheduled) >= len(items):
                        break

                if not high_pool and not low_items:
                    break

            # Append any remaining items (should be rare).
            for pool in (high_pool, low_items):
                for item_dec in pool:
                    scheduled.append(item_dec[0])

            # Ensure we do not lose or duplicate items.
            if len(scheduled) == len(items):
                scheduled_items = scheduled
        except Exception:
            scheduled_items = items
    else:
        scheduled_items = items

    successes = 0
    errors: list[str] = []

    with db.transaction():
        for item in scheduled_items:
            code = item.read_source(repo_root)

            # Add content type header
            header_lines = [f"[CONTENT_TYPE: {item.slice_type}]"]
            if item.slice_language:
                header_lines.append(f"[LANGUAGE: {item.slice_language}]")

            code_with_header = "\n".join(header_lines) + "\n\n" + code

            prompt = {
                "span_hash": item.span_hash,
                "path": str(item.file_path),
                "lang": item.lang,
                "lines": [item.start_line, item.end_line],
                "code": code_with_header,
                "instructions": "Return ONLY valid JSON per schema. Cite exact line ranges for every claim. If unsure, use null.",
            }
            try:
                response = llm_call(prompt)
            except Exception as exc:  # pragma: no cover - depends on user llm callable
                errors.append(f"{item.span_hash}: LLM call failed - {exc}")
                continue

            ok, validation_errors = validate_enrichment(
                response, item.start_line, item.end_line, enforce_latin1=enforce_latin1
            )
            if not ok:
                errors.append(
                    f"{item.span_hash}: validation failed - {', '.join(validation_errors) or 'unknown error'}"
                )
                continue

            payload = {
                **response,
                "model": model,
                "schema_version": response.get("schema_version", "enrichment.v1"),
                "content_type": item.slice_type,
                "content_language": item.slice_language or item.lang,
                "content_type_confidence": item.classifier_confidence,
                "content_type_source": "deterministic_classifier_v1",
            }
            db.store_enrichment(item.span_hash, payload)
            successes += 1

    return successes, errors


def _within_range(lines: list[int], start: int, end: int) -> bool:
    if len(lines) != 2:
        return False
    a, b = lines
    return start <= a <= end and start <= b <= end


def validate_enrichment(
    payload: dict[str, Any],
    span_start: int,
    span_end: int,
    enforce_latin1: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
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

    if enforce_latin1:
        text_fields = ["summary_120w", "usage_snippet"]
        for field in text_fields:
            val = payload.get(field)
            if isinstance(val, str) and not _is_latin1_safe(val):
                errors.append(f"{field} contains non-Latin-1 characters")

        list_fields = ["inputs", "outputs", "side_effects", "pitfalls"]
        for field in list_fields:
            items = payload.get(field, [])
            if isinstance(items, list):
                for i, item in enumerate(items):
                    if isinstance(item, str) and not _is_latin1_safe(item):
                        errors.append(f"{field}[{i}] contains non-Latin-1 characters")

    return len(errors) == 0, errors
