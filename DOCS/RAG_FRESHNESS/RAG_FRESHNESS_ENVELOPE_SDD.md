# SDD – LLMC RAG Result Envelope (Step 1)

## 1. Problem / Motivation

The LLMC RAG stack is gaining:

- A RAG Nav graph with schema-enriched entities/relations.
- Freshness metadata (`IndexStatus`, `FreshnessState`).
- A context gateway that will route between RAG vs. local deterministic fallbacks.

However, current tool handlers and CLIs return ad-hoc Python objects or JSON structures. There is no single, shared envelope that:

- Conveys whether a result is authoritative vs. fallback vs. error.
- Attaches freshness metadata in a consistent way.
- Is friendly for MCP servers and Desktop Commander to consume.

This makes it harder to:

- Safely fail over to deterministic methods (filesystem/AST) when RAG is stale.
- Expose structured, inspectable errors to callers instead of just exceptions.
- Implement future features like per-file `mtime` guards and slice-based routing.

## 2. Goals & Non-Goals

### Goals (Step 1)

- Introduce a **shared result envelope** for RAG navigation-style tools:
  - `RagToolMeta` – status + freshness metadata.
  - `RagResult[T]` – generic container for items and meta.
- Provide helper constructors for:
  - Success / OK results.
  - Deterministic fallback results.
  - Structured error results.
- Keep this entirely internal for now:
  - No changes to existing CLI or MCP behavior in Step 1.

### Non-Goals (Step 1)

- No changes to:
  - `tools.rag_nav.tool_handlers` return types.
  - `tools.rag.cli` options or JSON formats.
  - RAG daemon, MCP servers, or Desktop Commander.
- No new network calls, sidecar schema changes, or DB migrations.

Those will come in later steps.

## 3. High-Level Design

We introduce a small, focused module:

- `tools/rag/nav_meta.py`

This module defines:

1. Status / source types:

   ```python
   RagToolStatus = Literal["OK", "FALLBACK", "ERROR"]
   RagToolSource = Literal["RAG_GRAPH", "LOCAL_FALLBACK", "NONE"]
   ```

2. RAG tool metadata:

   ```python
   @dataclass
   class RagToolMeta:
       status: RagToolStatus = "OK"
       error_code: Optional[str] = None
       message: Optional[str] = None

       source: RagToolSource = "RAG_GRAPH"
       freshness_state: FreshnessState = "UNKNOWN"

       index_status: Optional[IndexStatus] = None

       def to_dict(self) -> dict:
           data = asdict(self)
           if self.index_status is not None and hasattr(self.index_status, "to_dict"):
               data["index_status"] = self.index_status.to_dict()
           return data
   ```

3. Generic result envelope:

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

4. Helper constructors:

   ```python
   def ok_result(
       items: Sequence[T],
       *,
       source: RagToolSource = "RAG_GRAPH",
       freshness_state: FreshnessState = "FRESH",
       index_status: Optional[IndexStatus] = None,
       message: Optional[str] = None,
   ) -> RagResult[T]:
       ...


   def fallback_result(
       items: Sequence[T],
       *,
       freshness_state: FreshnessState = "STALE",
       index_status: Optional[IndexStatus] = None,
       message: Optional[str] = None,
   ) -> RagResult[T]:
       ...


   def error_result(
       *,
       error_code: str,
       message: str,
       freshness_state: FreshnessState = "UNKNOWN",
       index_status: Optional[IndexStatus] = None,
   ) -> RagResult[dict]:
       ...
   ```

## 4. Detailed Behavior

### 4.1. Status & Source Semantics

- `status`:
  - `"OK"` – the result is authoritative and fully RAG-backed.
  - `"FALLBACK"` – the result came from a deterministic fallback path (filesystem/AST/grep), not the RAG index.
  - `"ERROR"` – the request could not be satisfied; see `error_code` / `message`.

- `source`:
  - `"RAG_GRAPH"` – data ultimately came from the RAG graph/index.
  - `"LOCAL_FALLBACK"` – data came from local deterministic methods.
  - `"NONE"` – no data could be returned (error path).

### 4.2. Freshness & IndexStatus Attachment

- `freshness_state`:
  - Uses the existing `FreshnessState` enum, e.g. `"FRESH"`, `"STALE"`, `"UNKNOWN"`.
- `index_status`:
  - Optional snapshot of the `IndexStatus` used when making the route decision.
  - Included in the meta to aid debugging and future MCP clients.

### 4.3. Serialization

- `RagToolMeta.to_dict()`:
  - Uses `asdict` for the dataclass.
  - If `index_status` has a `to_dict()` method, uses that to avoid deeply nested dataclasses.
- `RagResult.to_dict()`:
  - Serializes `meta` via `meta.to_dict()`.
  - Serializes each item via:
    - `item.to_dict()` if available.
    - `item._asdict()` for namedtuples.
    - Falls back to `item` as-is.

This keeps the envelope flexible for different item types without coupling it to specific models.

## 5. Integration Plan

Step 1 deliberately does **not** wire this into existing CLIs or tools. The plan is:

1. Implement and land `tools/rag/nav_meta.py`.
2. (Later) Update RAG Nav handlers to:
   - Construct `RagResult[...]` internally.
   - Use `ok_result` / `fallback_result` / `error_result` based on the gateway decision.
3. (Later) Wrap MCP and `--json` CLIs to:
   - Return `RagResult.to_dict()` as their JSON surface.
4. (Later) Extend the envelope to include per-slice or per-file freshness metadata if needed.

## 6. Testing Strategy

Step 1 testing is intentionally light:

- A small unit test module `tools/rag/tests/test_nav_meta.py` that:
  - Constructs `ok_result`, `fallback_result`, and `error_result`.
  - Checks `meta.status`, `meta.source`, and `items`.
  - Asserts `to_dict()` produces the expected structure.
- Import smoke test:
  - `python -m tools.rag.nav_meta` should not raise `ImportError`.

No integration tests are required yet since no runtime behavior changes.

## 7. Risks & Mitigations

- **Risk:** Future changes to `IndexStatus` could complicate `to_dict()` behavior.
  - **Mitigation:** Keep `RagToolMeta.to_dict()` defensive and tolerant of missing `to_dict()` methods.

- **Risk:** Envelope might diverge from MCP server expectations.
  - **Mitigation:** Treat this as an internal type for now; adjust as we wire MCP and Desktop Commander.

## 8. Acceptance Criteria

- `tools/rag/nav_meta.py` exists and imports cleanly.
- `RagToolMeta`, `RagResult`, and helper functions behave as expected in unit tests.
- No changes to existing CLI or RAG behavior in this step.

