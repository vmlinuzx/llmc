
# SDD – Phase 1, Change 3: Minimal Robust Fence Detection

## Summary
Replace naive backtick search with a minimal but robust fence detector that:
- Recognizes openers at line start with optional language tag (```python).
- Requires a matching closing fence.
- Supports multiple fenced blocks in a single query.

## Behavior
- If at least one complete fenced block is found, classify as code with high confidence.
- Inline single backticks do **not** count as fences.

## Notes
This is intentionally lightweight—full mixed-content parsing is deferred to Phase 3.
