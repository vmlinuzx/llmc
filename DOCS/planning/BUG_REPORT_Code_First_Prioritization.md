# Bug Report: Code-First Prioritization Not Working

**Date:** 2025-12-03  
**Severity:** P1 - High  
**Status:** Identified  

## Summary

The weighted file enrichment prioritization (code-first) is not working as intended. Instead of showing a 5:1 ratio of `.py` files to `.md` files, the enrichment service is processing entire markdown files sequentially.

## Observed Behavior

Looking at the last 30 enrichments, they're ALL from:
- `scripts/rag/README.md`
- `scripts/rag/TESTING.md`

Not a single `.py` file is being enriched, despite the code-first prioritization being enabled.

## Expected Behavior

With code-first prioritization enabled (5:1 ratio), we should see:
- Mostly `.py` files (weight 1-3) being enriched
- Occasional `.md` files (weight 7-8) interspersed
- Approximately 5 code files for every 1 documentation file

## Root Cause

The bug is in **`tools/rag/database.py`**, specifically the `pending_enrichments()` method (lines 354-393).

### The Problem

```python
def pending_enrichments(self, limit: int = 32, cooldown_seconds: int = 0) -> list[SpanWorkItem]:
    candidate_limit = max(limit * 5, limit)
    rows = self.conn.execute(
        """
        SELECT spans.span_hash, files.path, files.lang, spans.start_line,
               spans.end_line, spans.byte_start, spans.byte_end, files.mtime,
               spans.slice_type, spans.slice_language, spans.classifier_confidence
        FROM spans
        JOIN files ON spans.file_id = files.id
        LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
        WHERE enrichments.span_hash IS NULL
        ORDER BY spans.id  # ← THIS IS THE BUG
        LIMIT ?
        """,
        (candidate_limit,),
    ).fetchall()
```

**The query orders by `spans.id`**, which is the **insertion order**, not by any priority.

### Why This Breaks Code-First

1. The `EnrichmentPipeline._get_pending_spans()` method (lines 256-372 in `enrichment_pipeline.py`) does implement code-first prioritization
2. However, it only operates on items **already fetched** from the database
3. The pipeline fetches `limit * 2` items (e.g., 100 items for limit=50)
4. If those 100 items are all from the same file(s) due to insertion order, prioritization can't help

### Evidence from Database

```sql
-- Markdown files have consecutive IDs:
scripts/rag/README.md  → span IDs 4614-4623 (10 spans)
scripts/rag/TESTING.md → span IDs 4624-4630 (7 spans)

-- When the enrichment service fetches 50 items starting from ID 4614,
-- it gets ALL the README.md spans, then ALL the TESTING.md spans,
-- then maybe a few more files in that ID range.
```

The code-first prioritization can only shuffle these 50 items, but if they're all markdown files, there's nothing to prioritize!

## Impact

- **Enrichment quality**: Documentation files are being enriched before critical code files
- **User experience**: The "code-first" feature appears broken
- **Resource waste**: LLM tokens spent on low-priority content first

## Proposed Fix

### Option 1: Database-Level Prioritization (Recommended)

Modify `pending_enrichments()` to incorporate path weights directly in the SQL query:

```python
def pending_enrichments(self, limit: int = 32, cooldown_seconds: int = 0) -> list[SpanWorkItem]:
    # Fetch a diverse sample using RANDOM() or weighted ordering
    # This ensures we get a mix of file types, not just sequential IDs
    
    rows = self.conn.execute(
        """
        SELECT spans.span_hash, files.path, files.lang, spans.start_line,
               spans.end_line, spans.byte_start, spans.byte_end, files.mtime,
               spans.slice_type, spans.slice_language, spans.classifier_confidence
        FROM spans
        JOIN files ON spans.file_id = files.id
        LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
        WHERE enrichments.span_hash IS NULL
        ORDER BY RANDOM()  # Get a random sample for diversity
        LIMIT ?
        """,
        (limit * 10,),  # Fetch more to allow prioritization to work
    ).fetchall()
    
    # Then apply code-first prioritization in Python
    # (existing logic in EnrichmentPipeline)
```

**Pros:**
- Ensures diversity in the fetched items
- Allows code-first prioritization to actually work
- Minimal code changes

**Cons:**
- `RANDOM()` has performance implications on large tables
- Need to fetch more items than needed

### Option 2: Weighted SQL Query

Implement path weight scoring directly in SQL:

```python
def pending_enrichments(
    self, 
    limit: int = 32, 
    cooldown_seconds: int = 0,
    weight_config: dict[str, int] | None = None
) -> list[SpanWorkItem]:
    # Build a CASE statement for path weights
    # ORDER BY computed weight, then by ID for determinism
    
    # This requires passing weight_config to the database layer
    # More complex but more efficient
```

**Pros:**
- Most efficient (single query)
- Deterministic ordering

**Cons:**
- Requires passing weight config to database layer
- More complex SQL generation
- Harder to test

### Option 3: Increase Fetch Multiplier

Quick fix: Increase the fetch multiplier in `_get_pending_spans()`:

```python
# Line 262 in enrichment_pipeline.py
fetch_limit = limit * 10 if self.code_first else limit  # Was: limit * 2
```

**Pros:**
- One-line fix
- No database changes

**Cons:**
- Wasteful (fetches 10x more data than needed)
- Doesn't solve the fundamental problem
- Still fails if 500 consecutive spans are all markdown

## Recommendation

**Implement Option 1** as an immediate fix:
1. Change `ORDER BY spans.id` to `ORDER BY RANDOM()` in `pending_enrichments()`
2. Increase `candidate_limit` to `limit * 10` to ensure diversity
3. Let the existing code-first prioritization logic do its job

Then, **plan Option 2** for a future optimization milestone.

## Testing

After fix, verify:
1. Run enrichment service for 30 spans
2. Check that we see approximately 25 `.py` files and 5 `.md` files (5:1 ratio)
3. Verify that high-priority paths (weight 1-3) are enriched first
4. Confirm that low-priority paths (weight 7-10) appear occasionally

## Related Files

- `tools/rag/database.py` (line 354-393) - `pending_enrichments()` method
- `tools/rag/enrichment_pipeline.py` (line 256-372) - `_get_pending_spans()` method
- `llmc/enrichment/classifier.py` - Path weight classification logic
- `llmc.toml` (line 357-389) - Path weight configuration

## References

- Roadmap item 1.2.1: "Enrichment Path Weights & Code-First Prioritization"
- SDD: `DOCS/planning/SDD_Enrichment_Path_Weights.md`
- Previous conversation: "Validate Enrichment Path Weights" (2025-12-03)
