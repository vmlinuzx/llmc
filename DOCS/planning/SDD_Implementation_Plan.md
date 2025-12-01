# SDD Implementation Plan: Enrichment Router v2.1

**Status:** Planned
**Target:** `scripts/qwen_enrich_batch.py`, `tools/rag/enrichment_router.py`, Tests
**Goal:** Implement SDD v2.1 and fix "Ruthless Test Report" critical failures.

## 1. Fix Critical Test Failures

### 1.1 Fix `test_te_enrichment_manual.py` (Database Schema Mismatch)
- **Issue:** Test expects `profile` column in `embeddings` table, but code uses `profile_name`.
- **Fix:** Update test to query `profile_name` instead of `profile`.

### 1.2 Fix `test_enrichment_spanhash_and_fallbacks.py` (Enrichment None)
- **Issue:** Test uses a manual sqlite schema that lacks `content_type` and `content_language` columns, causing `sqlite3.OperationalError` inside `tools/rag_nav/enrichment.py`, which is caught silently, resulting in no enrichment attachment.
- **Fix:** Update `make_db_with_span` and `test_fallback_line_then_path` in the test file to include these missing columns in `CREATE TABLE` and `INSERT` statements.

### 1.3 Fix `test_routing_comprehensive.py` (API Mismatch)
- **Issue:** `classify_query` output format changed (returning `code-structure=...` reasons), breaking strict string matching in tests.
- **Fix:** Update test assertions to accept the new reason format.

## 2. Implement SDD v2.1 in `qwen_enrich_batch.py`

### 2.1 Integrate `EnrichmentRouter`
- **Current State:** Script loads the router but ignores it in the main loop, using legacy logic.
- **Changes:**
    1. In the main loop (`while True`), construct `EnrichmentSliceView` from the `item`.
    2. Call `enrichment_router.choose_chain(slice_view, chain_override=args.chain_name)`.
    3. Use the returned `EnrichmentRouteDecision` to:
        - Get `backend_specs`.
        - Build the cascade using these specs (refactoring `_build_cascade_for_attempt`).
        - Log the routing decision.

### 2.2 Refactor `_build_cascade_for_attempt`
- Modify to accept `EnrichmentRouteDecision` or `backend_specs` directly, reducing reliance on legacy `PRESET_CACHE` when routing is active.

## 3. Verify
- Run the 3 fixed tests.
- Run `test_enrichment_router_basic.py`.
- Run `test_p0_acceptance.py` (should pass after 1.2 is fixed).

## 4. Execution Order
1. Fix Tests (1.1, 1.2, 1.3).
2. Verify fixes.
3. Implement Router Integration (2.1, 2.2).
4. Verify Router.
