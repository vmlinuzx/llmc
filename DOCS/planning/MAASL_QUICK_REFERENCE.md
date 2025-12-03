# MAASL Quick Reference Card

## What is MAASL?
**Multi-Agent Anti-Stomp Layer** - prevents concurrent agents from corrupting each other's work.

## Core Components (Phase 1 ✅)

### Import Pattern
```python
from llmc_mcp.maasl import (
    get_maasl,
    ResourceDescriptor,
    ResourceBusyError,
)
```

### Basic Usage
```python
# Get MAASL instance
maasl = get_maasl()

# Define protected resource
resource = ResourceDescriptor(
    resource_class="CRIT_CODE",  # or CRIT_DB, MERGE_META, IDEMP_DOCS
    identifier="/path/to/file.py"  # or DB name, graph ID, etc.
)

# Execute with protection
def my_operation():
    # Your code here
    return "result"

result = maasl.call_with_stomp_guard(
    op=my_operation,
    resources=[resource],
    intent="write_file",
    mode="interactive",  # or "batch"
    agent_id="agent1",
    session_id="session1",
)
```

## Resource Classes

| Class | Use For | Lock Type | TTL | Max Wait |
|-------|---------|-----------|-----|----------|
| CRIT_CODE | File writes | mutex | 30s | 500ms |
| CRIT_DB | RAG database | single_writer | 60s | 1000ms |
| MERGE_META | Knowledge graph | merge | 30s | 500ms |
| IDEMP_DOCS | Documentation | idempotent | 120s | 500ms |

## Error Handling
```python
try:
    result = maasl.call_with_stomp_guard(...)
except ResourceBusyError as e:
    # Lock timeout
    print(f"Resource busy: {e.resource_key}")
    print(f"Held by: {e.holder_agent_id}")
except DbBusyError as e:
    # Database lock timeout
    print(f"DB busy: {e.description}")
except MaaslInternalError as e:
    # Unexpected error
    print(f"Internal error: {e.message}")
```

## Multiple Resources
```python
# Locks acquired in sorted order (deadlock prevention)
resources = [
    ResourceDescriptor("CRIT_CODE", "/zeta.py"),
    ResourceDescriptor("CRIT_CODE", "/alpha.py"),
    ResourceDescriptor("CRIT_DB", "rag"),
]

# Will lock: code:/alpha.py, code:/zeta.py, db:rag
result = maasl.call_with_stomp_guard(
    op=my_operation,
    resources=resources,
    ...
)
```

## Introspection (Phase 7 - Not Yet Implemented)
```python
from llmc_mcp.locks import get_lock_manager

mgr = get_lock_manager()

# View active locks
snapshot = mgr.snapshot()
for lock in snapshot:
    print(f"{lock['resource_key']}: held by {lock['holder_agent_id']}")
    print(f"  Duration: {lock['held_duration_ms']}ms")
    print(f"  TTL remaining: {lock['ttl_remaining_sec']}s")
```

## Configuration (llmc.toml)
```toml
[maasl]
enabled = true
default_interactive_max_wait_ms = 500
default_batch_max_wait_ms = 5000

[maasl.resource.CRIT_CODE]
lease_ttl_sec = 30
interactive_max_wait_ms = 500
```

## Testing with MAASL
```python
import pytest
from llmc_mcp.maasl import get_maasl, ResourceDescriptor, ResourceBusyError

@pytest.mark.allow_sleep  # Required for tests using time.sleep
def test_my_feature():
    maasl = get_maasl()
    # ... test code
```

## Current Status

✅ **Implemented (Phases 1-3):**
- Core locking mechanism
- Resource policies
- Exception hierarchy
- Telemetry
- **MCP tool wrappers**
- **File write protection**

📋 **Next (Phase 4):**
- DB transaction guards
- RAG write protection

📋 **Future:**
- Graph merge engine
- Docgen coordination
- Admin tools


## Key Design Principles

1. **Sorted Lock Acquisition:** Prevents deadlocks
2. **Fencing Tokens:** Prevents ABA problem
3. **Lease TTL:** Automatic cleanup
4. **Fail Fast:** Timeout quickly in interactive mode
5. **Telemetry:** All events logged

## When to Use MAASL

✅ **Use for:**
- File writes (code, config)
- Database writes (RAG enrichment)
- Knowledge graph updates
- Documentation generation

❌ **Don't use for:**
- Read-only operations
- Pure computation
- Single-threaded scripts

## Common Patterns

### Pattern 1: Write File with Protection
```python
def write_file_protected(path: str, content: str):
    maasl = get_maasl()
    resource = ResourceDescriptor("CRIT_CODE", path)
    
    def op():
        with open(path, 'w') as f:
            f.write(content)
        return path
    
    return maasl.call_with_stomp_guard(
        op=op,
        resources=[resource],
        intent="write_file",
        mode="interactive",
        agent_id="my_agent",
        session_id="my_session",
    )
```

### Pattern 2: DB Write with Protection
```python
def db_write_protected(data):
    maasl = get_maasl()
    resource = ResourceDescriptor("CRIT_DB", "rag")
    
    def op():
        # Your DB write logic
        conn.execute("INSERT ...")
        conn.commit()
        return "success"
    
    return maasl.call_with_stomp_guard(
        op=op,
        resources=[resource],
        intent="rag_enrich",
        mode="batch",  # Longer timeout for batch ops
        agent_id="enrichment_worker",
        session_id="batch_001",
    )
```

## Debug Tips

1. **Check locks:** `get_lock_manager().snapshot()`
2. **View telemetry:** Check stderr for structured logs
3. **Test contention:** Run multiple agents concurrently
4. **Verify cleanup:** Ensure all locks released (snapshot empty)

## Architecture Files

- **SDD:** `DOCS/planning/HLD_agentic_anti_stomp/SDD - MCP Multi-Agent Anti-Stomp Layer MAASL.md`
- **Implementation Plan:** `DOCS/planning/IMPL_MAASL_Anti_Stomp.md`
- **Session Summary:** `DOCS/planning/SESSION_SUMMARY_MAASL_Phase1.md`

## Source Code

- **Facade:** `llmc_mcp/maasl.py`
- **Locks:** `llmc_mcp/locks.py`
- **Telemetry:** `llmc_mcp/telemetry.py`
- **Tests:** `tests/test_maasl_locks.py`, `tests/test_maasl_facade.py`

---

**Version:** Phase 1 Complete  
**Last Updated:** December 2, 2025  
**Branch:** `feature/maasl-anti-stomp`
