# LLMC RAG Nav Tests - Quick Start Guide

## Overview
Comprehensive test suite for LLMC RAG Nav (Tasks 1-4) covering 7 categories with 22 tests total.

## Quick Test Run

```bash
# Run all tests (recommended)
python3 test_rag_nav_comprehensive.py

# Run with verbose output
python3 test_rag_nav_comprehensive.py --verbose

# Run specific test category
python3 test_rag_nav_comprehensive.py --filter="test_index_status"

# Check exit code for CI/CD
python3 test_rag_nav_comprehensive.py && echo "SUCCESS" || echo "FAILED"
```

## Test Categories

### Task 1: Index Status Metadata (4 tests)
- Status file save/load round-trip
- Missing file handling (returns None)
- Corrupt JSON handling (safe defaults)
- Multi-repo status isolation

### Task 2: Graph Builder CLI (4 tests)
- CLI help output and ergonomics
- Small repo graph creation
- Idempotent rebuild behavior
- Failure handling (preserve old graph)

### Task 3: Search/Where-Used/Lineage (4 tests)
- Search result format validation
- Where-used finds all call sites
- Lineage placeholder for incomplete features
- Error handling for unknown symbols

### Task 4: Context Gateway & Routing (3 tests)
- Routing rules (graph vs RAG preference)
- Freshness check (stale index detection)
- Degradation (missing graph handling)

### Task 5: CLI/MCP Tools (2 tests)
- CLI tools accept common flags
- JSON output support

### Task 6: Cross-Component Consistency (2 tests)
- File/path consistency across components
- ID consistency (stable IDs across systems)

### Task 7: End-to-End Scenarios (3 tests)
- Simple where-used workflow
- Multi-hop lineage (if implemented)
- Failure reporting and debugging

## Current Implementation Status

### ✅ Implemented & Passing (7 tests)
- Task 1: Index Status (4/4 passed - 100%)
- Task 6: Cross-Component Consistency (2/2 passed - 100%)
- Partial Task 2: Graph failure handling

### 🚧 Not Yet Implemented (15 tests)
- tools.rag_nav module structure
- CLI commands
- Search/where-used/lineage functionality
- Routing layer

## What Gets Tested

Each test creates:
- Temporary isolated repository
- Python modules with known symbols
- Import/call relationships for testing

Then verifies:
- Command execution
- JSON artifact formats
- Data structure consistency
- Error handling

## Test Output

### Console Output
```
✓ PASS [Category] TestName: Description
✗ FAIL [Category] TestName: Description
  Details: {json}
```

### Files Created
- `rag_nav_test_report.json` - Detailed JSON results
- `RAG_NAV_TEST_SUMMARY.md` - Comprehensive summary
- `RAG_NAV_TESTS_QUICK_START.md` - This guide

### JSON Report Structure
```json
{
  "summary": {
    "total": 22,
    "passed": 7,
    "failed": 15,
    "success_rate": 31.8
  },
  "by_category": {
    "Task 1: Index Status": {"passed": 4, "failed": 0, "total": 4},
    "Task 2: Graph Builder CLI": {"passed": 1, "failed": 3, "total": 4},
    ...
  },
  "tests": [...]
}
```

## Expected Behavior

### Before Implementation (Current)
```
Total Tests: 22
Passed: 7 (31.8%)
Failed: 15

BY CATEGORY:
  Task 1: Index Status: 4/4 passed (100%)      ✅
  Task 6: Cross-Component Consistency: 2/2 passed (100%)  ✅
  Task 2: Graph Builder CLI: 1/4 passed (25%)  ⚠️
  Task 3: Search/Where-Used/Lineage: 0/4 passed (0%)     ❌
  Task 4: Context Gateway: 0/3 passed (0%)    ❌
  Task 5: CLI/MCP Tools: 0/2 passed (0%)      ❌
  Task 7: End-to-End: 0/3 passed (0%)         ❌
```

### After Implementation (Target)
```
Total Tests: 22
Passed: 22 (100%)
Failed: 0

BY CATEGORY:
  Task 1: Index Status: 4/4 passed (100%)      ✅
  Task 2: Graph Builder CLI: 4/4 passed (100%) ✅
  Task 3: Search/Where-Used/Lineage: 4/4 passed (100%) ✅
  Task 4: Context Gateway: 3/3 passed (100%)   ✅
  Task 5: CLI/MCP Tools: 2/2 passed (100%)     ✅
  Task 6: Cross-Component Consistency: 2/2 passed (100%) ✅
  Task 7: End-to-End: 3/3 passed (100%)        ✅
```

## Environment Requirements

- Python 3.x with virtual environment
- LLMC repo at `/home/vmlinux/src/llmc`
- All RAG dependencies installed
- No existing `.llmc/rag*` conflicts in test locations

## Troubleshooting

### "ModuleNotFoundError: No module named 'tools.rag_nav'"
**Status**: Expected - module not yet implemented
**Action**: Tests validate format without module

### "File exists" errors in multi-repo test
**Status**: Temp directory conflict
**Action**: Tests auto-cleanup, retry if needed

### CLI script syntax errors
**Status**: Wrapper exists but module missing
**Action**: Implement tools.rag_nav.cli module

### Tests timeout
**Status**: Commands hang waiting for module
**Action**: Expected before implementation

## Implementation Roadmap

### Phase 1: Core Modules
```python
# tools/rag_nav/models.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class IndexStatus:
    repo: str
    index_state: str
    last_indexed_at: str
    last_indexed_commit: Optional[str]
    schema_version: str
    last_error: Optional[str]

@dataclass
class SearchResult:
    items: List[Any]
    source: str
    freshness_state: str
```

### Phase 2: Metadata Operations
```python
# tools/rag_nav/metadata.py
def status_path(repo_root: Path) -> Path
def load_status(repo_root: Path) -> Optional[IndexStatus]
def save_status(repo_root: Path, status: IndexStatus) -> Path
```

### Phase 3: Tool Handlers
```python
# tools/rag_nav/tool_handlers.py
def build_graph_for_repo(repo_root: Path) -> IndexStatus
def tool_rag_search(query: str, repo_root: Path, limit: int) -> SearchResult
def tool_rag_where_used(symbol: str, repo_root: Path, limit: int) -> SearchResult
def tool_rag_lineage(symbol: str, direction: str, repo_root: Path, max_results: int) -> SearchResult
```

### Phase 4: Gateway & Routing
```python
# tools/rag_nav/gateway.py
@dataclass
class Route:
    use_rag: bool
    freshness_state: str
    status: Optional[IndexStatus]

def compute_route(repo_root: Path) -> Route
```

### Phase 5: CLI
```python
# tools/rag_nav/cli.py
import click

@click.group()
def cli():
    """RAG Nav CLI"""

@cli.command()
@click.option("--repo", required=True)
def build_graph(repo):
    """Build graph for repository"""

@cli.command()
@click.option("--symbol", required=True)
@click.option("--json", is_flag=True)
def search(symbol, json):
    """Search for symbols"""

@cli.command()
@click.option("--symbol", required=True)
@click.option("--file")
@click.option("--json", is_flag=True)
def where_used(symbol, file, json):
    """Find where symbol is used"""

@cli.command()
@click.option("--symbol", required=True)
@click.option("--direction", default="downstream")
@click.option("--json", is_flag=True)
def lineage(symbol, direction, json):
    """Get symbol lineage"""

@cli.command()
@click.option("--repo", required=True)
@click.option("--json", is_flag=True)
def status(repo, json):
    """Check index status"""
```

## Best Practices

1. **Run tests early and often** - Validate changes
2. **Use verbose mode for debugging** - See detailed output
3. **Check JSON report** - Get structured results
4. **Test against real artifacts** - Validate production data
5. **Implement incrementally** - Build modules one by one

## References

- **Test Suite**: `/home/vmlinux/src/llmc/test_rag_nav_comprehensive.py`
- **Test Report**: `/home/vmlinux/src/llmc/rag_nav_test_report.json`
- **Summary**: `/home/vmlinux/src/llmc/RAG_NAV_TEST_SUMMARY.md`
- **CLI Wrapper**: `scripts/llmc-rag-nav`
- **Artifacts**: `.llmc/rag_index_status.json`, `.llmc/rag_graph.json`

## Support

If tests fail:
1. Check console output for errors
2. Review `rag_nav_test_report.json`
3. Verify module implementation status
4. Ensure dependencies installed
5. Check artifact formats match spec

---

**Last Updated**: 2025-11-16
**Test Version**: 1.0
**RAG Nav Version**: Pre-implementation
