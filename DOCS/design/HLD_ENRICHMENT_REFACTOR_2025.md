# High Level Design - Core Enrichment Processes Refactor

**Date:** 2025-11-22  
**Status:** Draft for Review  
**Scope:** Full sweep refactor of core enrichment processes

---

## 1. Executive Summary

### Current State
The enrichment system has a **config-driven architecture in place** but is **incomplete**:
- ✅ Config loader (`tools/rag/config_enrichment.py`) - fully implemented, tested
- ✅ Backend cascade abstraction (`tools/rag/enrichment_backends.py`) - implemented, tested
- ✅ Schema validation (`tools/rag/workers.py`) - implemented
- ❌ **Missing**: Core enrichment pipeline functions in `tools/rag/enrichment.py`
- ❌ **Missing**: Integration of config-driven backends into `scripts/qwen_enrich_batch.py`
- ❌ **Blocked**: 18 integration tests skipped due to missing functions

### Refactor Goals
1. **Complete the enrichment pipeline** by implementing missing core functions
2. **Integrate config-driven backends** into the main enrichment script
3. **Enable all integration tests** to run and pass
4. **Maintain backward compatibility** with existing CLI and workflows

### Success Criteria
- [ ] All 18 skipped integration tests pass
- [ ] Config-driven backend chains work from `llmc.toml`
- [ ] CLI maintains existing flags (no breaking changes)
- [ ] Integration with `qwen_enrich_batch.py` complete
- [ ] No performance regressions

---

## 2. Architecture Overview

### Current Architecture (Partial)

```
┌─────────────────────────────────────────┐
│   scripts/qwen_enrich_batch.py          │
│   (Main enrichment orchestrator)        │
└──────────────┬──────────────────────────┘
               │
               ├─ Uses hardcoded models/tiers
               ├─ Legacy backend selection
               └─ Missing config integration
                      │
                      ▼
┌─────────────────────────────────────────┐
│   tools/rag/workers.py                  │
│   - execute_enrichment()                │
│   - enrichment_plan()                   │
│   - validate_enrichment()               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   tools/rag/enrichment.py               │
│   ✗ Missing: enrich_spans()             │
│   ✗ Missing: batch_enrich()             │
│   ✗ Missing: enrich_with_retry()        │
│   ✓ QueryAnalyzer                       │
│   ✓ HybridRetriever                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   tools/rag/config_enrichment.py        │
│   ✓ EnrichmentConfig                    │
│   ✓ EnrichmentBackendSpec               │
│   ✓ load_enrichment_config()            │
│   ✓ select_chain()                      │
│   ✓ filter_chain_for_tier()             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   tools/rag/enrichment_backends.py      │
│   ✓ BackendAdapter (Protocol)           │
│   ✓ BackendCascade                      │
│   ✓ BackendError                        │
│   ✓ AttemptRecord                       │
└─────────────────────────────────────────┘
```

### Target Architecture (Complete)

```
┌─────────────────────────────────────────┐
│   scripts/qwen_enrich_batch.py          │
│   (Updated with config integration)     │
└──────┬───────────────────┬──────────────┘
       │                   │
       │ Uses config       │ Falls back to
       ▼                   │ legacy mode
┌─────────────────────────────────────────┐
│   tools/rag/enrichment.py               │
│   ✓ enrich_spans()  [NEW]              │
│   ✓ batch_enrich()  [NEW]              │
│   ✓ enrich_with_retry() [NEW]          │
│   ✓ QueryAnalyzer                       │
│   ✓ HybridRetriever                     │
└──────┬───────────────────┬──────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────────────┐
│   tools/rag/workers.py                  │
│   - execute_enrichment()                │
│   - enrichment_plan()                   │
│   - validate_enrichment()               │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   tools/rag/config_enrichment.py        │
│   (unchanged - already complete)        │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   tools/rag/enrichment_backends.py      │
│   (unchanged - already complete)        │
└─────────────────────────────────────────┘
```

---

## 3. Implementation Plan

### Phase 1: Core Pipeline Functions
**Files to modify:** `tools/rag/enrichment.py`

**Functions to implement:**
1. `enrich_spans(db, span_hashes, config, chain_name=None)` - Enrich a list of spans
2. `batch_enrich(db, config, limit, chain_name=None)` - Batch enrich from plan
3. `enrich_with_retry(db, span_hash, config, max_retries)` - Retry wrapper

**Dependencies:**
- Use `EnrichmentConfig` from `config_enrichment.py`
- Use `BackendCascade` from `enrichment_backends.py`
- Call `execute_enrichment()` from `workers.py`

### Phase 2: Config Integration
**Files to modify:** `scripts/qwen_enrich_batch.py`

**Changes:**
1. Add CLI flags: `--chain-name`, `--chain-config`
2. Load `EnrichmentConfig` in `main()`
3. Update `_build_cascade_for_attempt()` to use config when available
4. Maintain backward compatibility (fallback to legacy mode)

### Phase 3: Testing & Validation
**Actions:**
1. Run integration tests - verify 18 skipped tests now pass
2. Test config-driven workflow with sample `llmc.toml`
3. Test backward compatibility (no config file)
4. Performance testing (ensure no regressions)

---

## 4. Key Design Decisions

### Decision 1: Where to implement core functions
**Choice:** `tools/rag/enrichment.py`  
**Rationale:**
- Tests already import from here
- Central location for enrichment logic
- Keeps related classes (QueryAnalyzer, HybridRetriever) together

### Decision 2: Config-driven vs Legacy mode
**Choice:** Support both modes with fallback  
**Rationale:**
- No breaking changes to existing workflows
- Gradual migration path for users
- Config missing → automatic fallback to legacy behavior

### Decision 3: Cascade integration strategy
**Choice:** Wrap `BackendCascade` in helper functions  
**Rationale:**
- Cleaner API for workers.py
- Easier to test in isolation
- Decouples cascade logic from DB operations

---

## 5. Risk Assessment

### High Risk
1. **Breaking existing CLI workflows**
   - **Mitigation:** Maintain all existing flags, add new ones as optional
   - **Test:** Run with empty config file (fallback mode)

2. **Performance regressions**
   - **Mitigation:** Keep existing fast path, only use config when present
   - **Test:** Benchmark before/after with same workload

### Medium Risk
1. **Test failures due to API mismatch**
   - **Mitigation:** Match expected API from integration tests exactly
   - **Test:** Run integration tests first to establish baseline

2. **Backend adapter compatibility**
   - **Mitigation:** Use existing adapters that are tested
   - **Test:** Verify cascade works with both ollama and gateway

### Low Risk
1. **Config parsing edge cases**
   - **Mitigation:** Already tested in `test_enrichment_config.py`
   - **Test:** Test with malformed config → should fallback

---

## 6. Test Strategy

### Unit Tests
- `test_enrichment_config.py` - Already passing (5/5)
- `test_enrichment_backends.py` - Already passing (2/2)
- `test_enrichment_cascade.py` - Already passing (3/3)
- `test_enrichment_adapters.py` - Already passing (4/4)

### Integration Tests
- `test_enrichment_integration.py` - 18 skipped (EXPECTED TO PASS AFTER REFACTOR)
- `test_enrichment_integration_edge_cases.py` - 47 passing
- `test_enrichment_data_integration_failure.py` - 3 passing

### Manual Testing
1. Run with sample `llmc.toml` config
2. Run without config (legacy mode)
3. Run with invalid config (should fallback)
4. Test backend failover in cascade

---

## 7. Timeline Estimate

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | 1-2 hours | Core functions in `enrichment.py` |
| Phase 2 | 1-2 hours | Config integration in batch script |
| Phase 3 | 30 min | Run tests, validate |
| **Total** | **3-4 hours** | **Complete refactor** |

---

## 8. Dependencies

### External
- None (all dependencies already in codebase)

### Internal
- `tools/rag/config_enrichment.py` - Already complete
- `tools/rag/enrichment_backends.py` - Already complete  
- `tools/rag/workers.py` - Already complete
- `scripts/qwen_enrich_batch.py` - Needs integration

---

## 9. Rollback Plan

If issues arise:

1. **Keep backup** of current `tools/rag/enrichment.py`
2. **Revert in order:**
   - Revert `scripts/qwen_enrich_batch.py` changes
   - Restore `tools/rag/enrichment.py` from backup
3. **Status:** Tests remain skipped but system functional

---

## 10. Success Metrics

### Quantitative
- [ ] 18 integration tests unskipped and passing
- [ ] 0 test failures introduced
- [ ] Config-driven mode working (verified with test config)

### Qualitative
- [ ] Code follows existing patterns
- [ ] No duplication with existing modules
- [ ] Documentation updated
