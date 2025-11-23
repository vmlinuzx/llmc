# Implementation Notes – Phase 1 Backend Abstraction

This phase adds the generic backend abstraction and cascade helper used by the
enrichment system.

- No changes are made to `scripts/qwen_enrich_batch.py` yet.
- The new module is provider-neutral and does not depend on router policy or DB.
- Tests cover basic success and all-fail behaviour of `BackendCascade`.
