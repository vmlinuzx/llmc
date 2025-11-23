# SDD – Phase 1: Base Enrichment Backend Abstraction & Cascade

## Overview

This phase introduces a small, self-contained abstraction layer for enrichment
backends and a generic cascade helper. It does not modify any existing scripts.
The goal is to create a clean foundation that later phases can wire into
`scripts/qwen_enrich_batch.py`.

## Design

- `AttemptRecord`: dataclass describing one backend attempt.
- `BackendError`: exception carrying `failure_type`, optional `attempts`, and
  optional provider-specific `failure` payload.
- `BackendAdapter`: Protocol with `.config`, `.generate()`, and
  `.describe_host()`.
- `BackendCascade`: orchestrator over an ordered list of backends that returns
  the first successful result or raises `BackendError` if all fail.

## Files

- `tools/rag/enrichment_backends.py`
- `tests/test_enrichment_backends.py`
