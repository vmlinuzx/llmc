
# SDD – Phase 1, Change 1: Normalize Input in `classify_query`

## Summary
Normalize incoming `text` so that `None` and whitespace-only inputs safely route to `docs` with low confidence and a clear reason, avoiding crashes and ambiguous behavior.

## Design
- Accept `Optional[str]` logically (annotation left as `str` for backward compatibility if needed).
- At function start:
  - Convert `None` → `""`.
  - Cast non-strings to `str` defensively.
  - If the normalized string is empty/whitespace-only, return:
    ```json
    {"route_name": "docs", "confidence": 0.2, "reasons": ["empty-or-none-input"]}
    ```

## Rationale
- Prevents runtime exceptions on `None`.
- Produces deterministic, low-risk routing for empty input.
- Provides a reason token to aid telemetry and debugging.

## Out of Scope
- Reordering heuristics and fence detection (Phase 1, Changes 2–3).
- Broader refactor, metrics, config surface (later phases).
