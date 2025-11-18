# RAG Freshness & Navigation Envelope - Test Plan

## 1. Objectives

This test suite validates the correctness and stability of LLMC's RAG freshness and navigation envelope system. Specifically:

- **Result envelope structure**: `RagToolMeta` and `RagResult[T]`
- **Freshness classification**: IndexStatus parsing and FreshnessState determination
- **Context routing decisions**: Future `compute_route` gateway behavior
- **Per-file mtime guard**: Future file-level staleness detection
- **Integration contracts**: Stable JSON shape for MCP and tool callers

**Non-goals**: LLM reasoning quality, output content correctness, daemon behavior.

## 2. Scope

### 2.1 In Scope

All behavior that determines:
- When RAG can be trusted (fresh vs stale vs unknown)
- What happens when RAG is stale or missing
- How these decisions are communicated via result envelopes
- Stability of JSON/MCP contract shapes

### 2.2 Out of Scope

- LLM reasoning or output quality
- Long-running daemon scheduling beyond deterministic simulation
- Actual graph database operations
- Network/LLM API calls

## 3. Test Categories

### 3.1 Unit Tests

**Objective**: Validate individual components in isolation

**Coverage**:
- `tools/rag/nav_meta.py`: RagToolMeta, RagResult, helper constructors
- `tools/rag/freshness.py`: IndexStatus, FreshnessState types
- Context gateway (when implemented): `compute_route` function
- Per-file mtime guard (when implemented): file-level staleness logic

**Characteristics**:
- No filesystem operations (except temp dirs)
- No network calls
- No LLM calls
- Deterministic and fast (<1s per test file)

### 3.2 Integration Tests

**Objective**: Validate tool-level contracts and JSON output shape

**Coverage**:
- RAG nav tool integration (search, where-used, lineage when available)
- JSON serialization/deserialization
- MCP output contract stability
- CLI output (when implemented)

**Characteristics**:
- Use fixture repos or temp directories
- Mock any external dependencies
- Validate both success and error paths

### 3.3 Contract Tests

**Objective**: Ensure backward-compatible API surface

**Coverage**:
- `RagResult.to_dict()` always produces stable schema
- `RagToolMeta.to_dict()` always has required fields
- Error codes are stable and documented
- Freshness states are from defined set

## 4. Test Implementation Details

### 4.1 Testing Framework

- **Framework**: pytest
- **Marker**: `@pytest.mark.rag_freshness`
- **Isolation**: Each test uses fresh fixtures/temp dirs

### 4.2 Directory Structure

```
tools/rag/tests/
├── __init__.py
├── test_nav_meta.py           # RagToolMeta, RagResult, helpers
├── test_freshness_index_status.py  # IndexStatus, FreshnessState
├── test_freshness_gateway.py       # compute_route (when ready)
├── test_file_mtime_guard.py        # per-file staleness (when ready)
└── test_nav_tools_integration.py   # tool-level integration tests
```

### 4.3 Key Test Scenarios

#### 4.3.1 Envelope Tests (test_nav_meta.py)

**RagToolMeta Basics**:
- Default values for status, source, freshness_state
- `to_dict()` serializes all fields including optional index_status
- Optional index_status handled correctly when None

**RagResult Serialization**:
- Simple types (str, int) serialize correctly
- Complex types with `to_dict()` method handled
- Namedtuple `_asdict()` support works
- Empty items handled gracefully

**Helper Constructors**:
- `ok_result()`: sets correct status, source, freshness_state
- `fallback_result()`: sets FALLBACK status, LOCAL_FALLBACK source
- `error_result()`: sets ERROR status, NONE source, requires error_code

#### 4.3.2 Freshness Tests (test_freshness_index_status.py)

**IndexStatus Construction**:
- Valid status with all required fields
- Optional last_error handling
- `to_dict()` includes last_error only when present

**Freshness Classification**:
- State "fresh" → FreshnessState "FRESH"
- State "stale" → FreshnessState "STALE"
- State "error" → FreshnessState "STALE" or "UNKNOWN" (document decision)
- State "rebuilding" → FreshnessState "UNKNOWN"

#### 4.3.3 Gateway Tests (test_freshness_gateway.py)

**Routing Scenarios**:
- No status file → use_rag=False, freshness_state="UNKNOWN"
- Status file with stale state → use_rag=False, freshness_state="STALE"
- Status file with fresh state but HEAD mismatch → use_rag=False, freshness_state="STALE"
- Status file with fresh state and matching HEAD → use_rag=True, freshness_state="FRESH"

**Note**: `compute_route` function not yet implemented in codebase.

#### 4.3.4 Integration Tests (test_nav_tools_integration.py)

**Tool Contract Validation**:
- Tools return RagResult envelopes
- meta.status reflects success/fallback/error
- meta.source indicates RAG_GRAPH vs LOCAL_FALLBACK
- meta.freshness_state matches index status
- JSON output has stable meta.items schema

**Note**: Navigation tools (search, where-used, lineage) not yet using RagResult in current codebase.

## 5. Test Data & Fixtures

### 5.1 Minimal Test Repo Structure

```
/tmp/test_repo_XXX/
├── file1.py
├── file2.py
└── .llmc/
    └── rag_index_status.json
```

### 5.2 Index Status Variants

1. **Fresh**:
   ```json
   {
     "repo": "test_repo",
     "index_state": "fresh",
     "last_indexed_at": "2025-11-16T10:00:00Z",
     "last_indexed_commit": "abc123",
     "schema_version": "1.0"
   }
   ```

2. **Stale**:
   ```json
   {
     "repo": "test_repo",
     "index_state": "stale",
     "last_indexed_at": "2025-11-15T10:00:00Z",
     "last_indexed_commit": "abc123",
     "schema_version": "1.0",
     "last_error": "Index out of date"
   }
   ```

3. **Missing**: No `.llmc/rag_index_status.json` file

## 6. Running the Tests

### 6.1 Command Line

```bash
# Run all RAG freshness tests
python -m pytest -m rag_freshness -v

# Run specific test file
python -m pytest tools/rag/tests/test_nav_meta.py -v

# Run with coverage
python -m pytest -m rag_freshness --cov=tools.rag.nav_meta --cov=tools.rag.freshness
```

### 6.2 Continuous Integration

Tests should run on:
- Every PR touching `tools/rag/*` or `DOCS/RAG_FRESHNESS/*`
- Nightly builds for regression detection

Failure conditions:
- Any test failure
- Unexpected changes to JSON contract shape
- New lint/type errors

## 7. Known Limitations

### 7.1 Not Yet Implemented

1. **Context Gateway (`compute_route`)**: No routing decision logic yet
2. **Per-file mtime Guard**: No file-level staleness detection
3. **RAG Navigation Tools**: Not yet integrated with RagResult envelopes
4. **CLI Integration**: No command-line tool using these envelopes

### 7.2 Testing Workarounds

- Mock `compute_route` function for integration tests
- Use direct RagResult construction for tool tests
- Create synthetic IndexStatus objects for envelope validation

## 8. Success Criteria

✅ **Test Suite Passes**: All tests green on clean checkout

✅ **No Regressions**: Envelope semantics remain stable

✅ **Fast Execution**: Full suite runs in <10 seconds

✅ **Offline Operation**: No network or LLM dependencies

✅ **Clear Failures**: Any contract breach causes loud, clear test failure

## 9. Maintenance

### 9.1 When Adding New Features

1. Add corresponding tests before/with implementation
2. Update this test plan document
3. Ensure backward compatibility of JSON contract

### 9.2 Contract Stability

Breaking changes to:
- `RagResult.to_dict()` schema
- `RagToolMeta` fields
- FreshnessState values
- Error codes

**Require**: Test updates + documentation updates + explicit approval

## 10. References

- Implementation: `tools/rag/nav_meta.py`
- Implementation: `tools/rag/freshness.py`
- Design docs: `DOCS/RAG_FRESHNESS/`
- Related: `tools/rag/graph.py`, `tools/rag/cli.py`

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16
**Owner**: LLMC Testing Agent
