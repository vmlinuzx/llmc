# Implementation Plan: Multi-Agent Anti-Stomp Layer (MAASL)

**Feature Branch:** `feature/maasl-anti-stomp`  
**Based on:** SDD in `DOCS/planning/HLD_agentic_anti_stomp/SDD - MCP Multi-Agent Anti-Stomp Layer MAASL.md`  
**Status:** ✅ Phases 1-6 Complete - Ready for Phase 7  
**Effort:** 15-22 hours (phased) | ~9 hours completed



---

## Objective

Build production-grade coordination layer to prevent concurrent agents from stomping on each other's work. Supports file locks, DB transaction guards, graph merges, and docgen coordination.

---

## Architecture Overview

```
llmc_mcp/
├── maasl.py              # MAASL facade (call_with_stomp_guard)
├── locks.py              # LockManager (mutex, leases, fencing)
├── db_guard.py           # DbTransactionManager
├── merge_meta.py         # MergeEngine (deterministic graph merge)
├── docgen_guard.py       # DocgenCoordinator (SHA gating)
└── telemetry.py          # TelemetrySink
```

---

## Resource Classes

| Class | Concurrency | Lock Scope | Strategy |
|-------|-------------|------------|----------|
| CRIT_CODE | mutex | file | fail_closed |
| CRIT_DB | single_writer | db | fail_closed |
| MERGE_META | merge | graph | fail_open_merge |
| IDEMP_DOCS | idempotent | repo | fail_closed |

---

## Implementation Phases

### Phase 1: Core Infrastructure (4-6 hours) ✅ COMPLETE
**Priority:** P0

**Tasks:**
- [x] Create module structure
- [x] Implement `ResourceClass` dataclass
- [x] Implement `LockManager` with:
  - Basic mutex per resource_key
  - Lease TTL and expiry checking
  - Fencing tokens (monotonic counter)
  - `acquire()`, `release()`, `snapshot()`
- [x] Implement `PolicyRegistry`
  - Resource class definitions
  - Config loading from llmc.toml
- [x] Basic telemetry (structured logging)

**Deliverables:**
- `llmc_mcp/maasl.py` (full facade with PolicyRegistry and exceptions) ✅
- `llmc_mcp/locks.py` (complete LockManager) ✅
- `llmc_mcp/telemetry.py` (full TelemetrySink) ✅
- Comprehensive unit tests (26 tests, all passing) ✅


---

### Phase 2: MAASL Facade (2-3 hours)
**Priority:** P0

**Tasks:**
- [ ] Implement `call_with_stomp_guard()`:
  - Resource resolution (descriptor → class)
  - Lock acquisition (sorted order for deadlock prevention)
  - Operation execution
  - Lock release
  - Error handling
- [ ] Define exception hierarchy:
  - `ResourceBusyError`
  - `DbBusyError`
  - `DocgenStaleError`
  - `StaleVersionError`
  - `MaaslInternalError`
- [ ] Telemetry integration (lock events, contention metrics)

**Deliverables:**
- Complete `maasl.py` facade
- Full error model

---

### Phase 3: Code Protection (3-4 hours) ✅ COMPLETE
**Priority:** P0

**Tasks:**
- [x] Wrap `write_file` MCP tool:
  - Acquire CRIT_CODE lock
  - Atomic write (temp + rename)
  - Release lock on completion
- [x] Wrap `refactor_file` / `edit_file` tools
- [x] Add lock timeout handling
- [x] Test concurrent writes (2+ agents)

**Deliverables:**
- Protected file write operations ✅
- Lock contention handling ✅
- Integration tests (12 tests, all passing) ✅

**Session:** December 2, 2025 (~2 hours)  
**Summary:** `DOCS/planning/SESSION_SUMMARY_MAASL_Phase3.md`


---

### Phase 4: DB Transaction Guard (2-3 hours) ✅ COMPLETE
**Priority:** P1

**Tasks:**
- [x] Implement `DbTransactionManager`:
  - Context manager for SQLite sessions
  - `BEGIN IMMEDIATE` for writes
  - Timeout on DB_BUSY
  - Transaction rollback on error
- [x] Wrap RAG enrichment tools:
  - `rag_enrich` uses DB guard
  - Serial writes to SQLite
- [x] Test concurrent DB writes

**Deliverables:**
- `llmc_mcp/db_guard.py` ✅
- Protected RAG DB operations ✅
- Integration tests (11 tests, all passing) ✅

**Session:** December 2, 2025 (~1.5 hours)


---

### Phase 5: Graph Merge Engine (3-4 hours) ✅ COMPLETE  
**Priority:** P2

**Tasks:**
- [x] Implement `MergeEngine`:
  - GraphPatch dataclass
  - Last-Write-Wins (LWW) semantics
  - Deterministic node/edge merge
  - Conflict logging
- [x] Wrap graph update operations
- [x] Test concurrent graph updates

**Deliverables:**
- `llmc_mcp/merge_meta.py` ✅
- Protected graph merging ✅
- Integration tests (10 tests, all passing) ✅

**Session:** December 2, 2025 (~20 minutes)

---

### Phase 6: Docgen Coordination (2-3 hours) ✅ COMPLETE
**Priority:** P1

**Tasks:**
- [x] Implement `DocgenCoordinator`:
  - SHA256 gating (check header before regen)
  - Repo-level mutex (docgen:repo)
  - Atomic doc writes
  - NO-OP when hash matches
- [x] Wrap `docgen_file` tool
- [x] Test concurrent docgen calls

**Deliverables:**
- `llmc_mcp/docgen_guard.py` ✅
- SHA-gated documentation ✅
- Integration tests (18 tests, all passing) ✅

**Session:** December 2, 2025 (~30 minutes)

---

### Phase 7: Introspection Tools (1-2 hours)
**Priority:** P2

**Tasks:**
- [ ] Add MCP tools:
  - `llmc.locks` - List active locks
  - `llmc.stomp_stats` - Contention metrics
  - `llmc.docgen_status` - Recent docgen runs
- [ ] Expose via MCP server

**Deliverables:**
- Admin/debug tools for operators

---

### Phase 8: Testing & Validation (3-4 hours)
**Priority:** P0

**Tasks:**
- [ ] Unit tests:
  - LockManager acquire/release/timeout
  - DbTransactionManager rollback
  - MergeEngine determinism
  - DocgenCoordinator SHA gating
- [ ] Integration tests:
  - 2 agents concurrent file writes
  - 3 agents concurrent rag_enrich
  - Concurrent docgen (one runs, others NO-OP)
- [ ] Load testing:
  - 5 agents, verify no stomps
  - Measure lock contention latency

**Deliverables:**
- Comprehensive test suite
- Performance validation

---

## Error Model

```python
class ResourceBusyError(Exception):
    """Lock acquisition timeout."""
    def __init__(self, resource_key, holder, wait_ms, max_wait_ms):
        ...

class DbBusyError(Exception):
    """SQLite lock timeout."""
    ...

class DocgenStaleError(Exception):
    """SHA mismatch on docgen."""
    ...

class StaleVersionError(Exception):
    """File version conflict."""
    ...

class MaaslInternalError(Exception):
    """Unexpected MAASL error."""
    ...
```

---

## Configuration (llmc.toml)

```toml
[maasl]
enabled = true
default_interactive_max_wait_ms = 500
default_batch_max_wait_ms = 5000
default_lease_ttl_sec = 30

[maasl.resource.CRIT_CODE]
lease_ttl_sec = 30
interactive_max_wait_ms = 500
batch_max_wait_ms = 3000

[maasl.resource.CRIT_DB]
lease_ttl_sec = 60
interactive_max_wait_ms = 1000
batch_max_wait_ms = 10000

[maasl.resource.MERGE_META]
lease_ttl_sec = 30

[maasl.resource.IDEMP_DOCS]
lease_ttl_sec = 120
```

---

## Rollout Strategy

### Phase 0: Telemetry Only (Optional)
- MAASL calls succeed but don't block
- Emit telemetry about *would-be* locks
- Validate no performance regression

### Phase 1: Code Protection
- Enable CRIT_CODE locks
- Test with 2-3 agents
- Monitor for issues

### Phase 2: Full Protection
- Enable all resource classes
- Monitor contention metrics
- Tune timeouts

---

## Success Criteria

- [ ] 5+ agents can work concurrently without stomps
- [ ] Lock acquisition < 500ms for interactive ops
- [ ] DB transactions complete < 1000ms
- [ ] Zero file corruptions under load
- [ ] Deterministic graph merges (no data loss)
- [ ] Clean lint after concurrent edits

---

## Timeline

| Phase | Effort | Difficulty | Dependencies |
|-------|--------|------------|--------------|
| 1. Core Infrastructure | 4-6h | 🟡 Medium | - |
| 2. MAASL Facade | 2-3h | 🟡 Medium | Phase 1 |
| 3. Code Protection | 3-4h | 🟢 Easy | Phase 2 |
| 4. DB Guard | 2-3h | 🟢 Easy | Phase 2 |
| 5. Graph Merge | 3-4h | 🟡 Medium | Phase 2 |
| 6. Docgen Coord | 2-3h | 🟢 Easy | Phase 2 |
| 7. Introspection | 1-2h | 🟢 Easy | Phases 1-6 |
| 8. Testing | 3-4h | 🟡 Medium | All |

**Total:** 20-29 hours (2-3 focused days)

---

## 🔥 FULL SEND MODE

We're going **straight to Phase 1** - no telemetry-only warmup. Build the real thing from the start.

**LET'S GO!** 💀
