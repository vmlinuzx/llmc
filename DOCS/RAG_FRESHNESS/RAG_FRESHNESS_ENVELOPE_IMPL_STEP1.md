# Implementation SDD – LLMC RAG Result Envelope (Step 1)

## 1. Objective

Implement the shared RAG result envelope (`RagToolMeta` + `RagResult`) described in the Step 1 SDD, without changing existing CLI behavior.

This prepares the codebase for:

- Context freshness routing (`compute_route`).
- Per-file `mtime` guards.
- Clean MCP / Desktop Commander contracts.

## 2. Files & Modules

### New

- `tools/rag/nav_meta.py`  
  New module containing:

  - Status / source type aliases.
  - `RagToolMeta` dataclass.
  - `RagResult[T]` generic envelope.
  - Helper constructors (`ok_result`, `fallback_result`, `error_result`).

### Optional New (for tests)

- `tools/rag/tests/test_nav_meta.py` (or whichever test layout you use).

### Existing (unchanged in Step 1)

- `tools/rag/freshness.py` – provides `FreshnessState` and `IndexStatus`.
- `tools/rag/types.py` – domain-specific RAG types (spans, files, etc.).
- `tools/rag/cli.py` – CLI entrypoints.
- Any future MCP server module in `mcp/` – will use these types in later steps.

## 3. Detailed Changes

### 3.1. `tools/rag/nav_meta.py`

Create this file with the following structure:

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Generic, Literal, Optional, Sequence, TypeVar

from .freshness import FreshnessState, IndexStatus

RagToolStatus = Literal["OK", "FALLBACK", "ERROR"]
RagToolSource = Literal["RAG_GRAPH", "LOCAL_FALLBACK", "NONE"]


@dataclass
class RagToolMeta:
    """
    Metadata attached to all RAG navigation-style tool responses.

    This is what MCP clients and Desktop Commander should inspect to decide
    whether the result is authoritative, a deterministic fallback, or an error.
    """
    status: RagToolStatus = "OK"
    error_code: Optional[str] = None
    message: Optional[str] = None

    source: RagToolSource = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"

    index_status: Optional[IndexStatus] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.index_status is not None:
            # Delegate to IndexStatus if it supports to_dict(); otherwise, rely on asdict.
            if hasattr(self.index_status, "to_dict"):
                data["index_status"] = self.index_status.to_dict()
        return data
```

Generic result envelope:

```python
T = TypeVar("T")


@dataclass
class RagResult(Generic[T]):
    meta: RagToolMeta
    items: Sequence[T] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        def _item_to_dict(item):
            if hasattr(item, "to_dict"):
                return item.to_dict()
            if hasattr(item, "_asdict"):
                return item._asdict()
            return item

        return {
            "meta": self.meta.to_dict(),
            "items": [_item_to_dict(item) for item in self.items],
        }
```

Helper constructors:

```python
def ok_result(
    items: Sequence[T],
    *,
    source: RagToolSource = "RAG_GRAPH",
    freshness_state: FreshnessState = "FRESH",
    index_status: Optional[IndexStatus] = None,
    message: Optional[str] = None,
) -> RagResult[T]:
    return RagResult(
        meta=RagToolMeta(
            status="OK",
            error_code=None,
            message=message,
            source=source,
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=items,
    )


def fallback_result(
    items: Sequence[T],
    *,
    freshness_state: FreshnessState = "STALE",
    index_status: Optional[IndexStatus] = None,
    message: Optional[str] = None,
) -> RagResult[T]:
    return RagResult(
        meta=RagToolMeta(
            status="FALLBACK",
            error_code=None,
            message=message,
            source="LOCAL_FALLBACK",
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=items,
    )


def error_result(
    *,
    error_code: str,
    message: str,
    freshness_state: FreshnessState = "UNKNOWN",
    index_status: Optional[IndexStatus] = None,
) -> RagResult[dict]:
    return RagResult(
        meta=RagToolMeta(
            status="ERROR",
            error_code=error_code,
            message=message,
            source="NONE",
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=(),
    )
```

### 3.2. Optional Tests

Create `tools/rag/tests/test_nav_meta.py` with minimal sanity checks:

```python
from tools.rag.nav_meta import (
    RagToolMeta,
    RagResult,
    ok_result,
    fallback_result,
    error_result,
)
from tools.rag.freshness import IndexStatus

def test_ok_result_basic():
    items = ["foo", "bar"]
    result = ok_result(items, message="test")
    assert result.meta.status == "OK"
    assert result.items == items
    d = result.to_dict()
    assert d["meta"]["status"] == "OK"
    assert d["items"] == items

def test_error_result_basic():
    result = error_result(
        error_code="RAG_UNAVAILABLE",
        message="Index missing",
        freshness_state="STALE",
    )
    assert result.meta.status == "ERROR"
    assert result.items == ()
    d = result.to_dict()
    assert d["meta"]["error_code"] == "RAG_UNAVAILABLE"
```

These are intentionally minimal – just enough to catch accidental refactors.

## 4. Rollout & Integration Notes

Step 1 does **not** wire this into existing CLI or MCP endpoints yet. Recommended rollout:

1. Land this module behind the scenes.
2. In Step 2 / 3 work, update specific tools (e.g., RAG Nav, where-used, lineage) to:
   - Internally build `RagResult[...]` envelopes.
   - Expose `result.to_dict()` for MCP / `--json` output modes.
   - Keep legacy human-readable CLI output for interactive use.

## 5. Acceptance Checklist

- [ ] `tools/rag/nav_meta.py` added and imports cleanly:
  - `python -m tools.rag.nav_meta` must not raise ImportError.
- [ ] Optional tests pass (if added).
- [ ] No changes to `tools/rag/cli.py` or other runtime behavior yet.
- [ ] Developers can construct and serialize example `RagResult` instances from a REPL.

