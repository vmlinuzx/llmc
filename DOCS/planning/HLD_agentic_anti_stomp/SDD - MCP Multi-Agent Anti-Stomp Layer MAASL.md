SDD - LLMC MCP Multi-Agent Anti-Stomp Layer (MAASL)
Version: 0.1
Date: 2025-12-02
Owner: LLMC
Status: Draft for implementation review

======================================================================
0. PURPOSE AND SCOPE

0.1 Purpose

This SDD defines the concrete software design for the Multi-Agent Anti-Stomp Layer (MAASL) inside llmc_mcp. MAASL coordinates concurrent access to shared LLMC resources (repo files, RAG SQLite database, knowledge graph JSON, generated docs) when multiple MCP clients and agents operate on the same repo.

The primary goal is to prevent stomp conditions (corrupting or overwriting each other’s work) while keeping interactive operations fast.

0.2 In Scope

In-process coordination layer inside llmc_mcp.

Locking, leasing, and fencing mechanisms for:

Code files

RAG SQLite database

Knowledge graph and metadata JSON

Generated documentation in DOCS / REPODOCS

MCP tool integration for stomp-aware operations.

Telemetry and basic introspection tools via MCP.

0.3 Out of Scope

Multi-host or distributed locking across machines.

Git workflows, branching, or merge policies.

Complex CRDT or collaborative editing for code.

Advanced policy engines or ACLs for which agent is allowed to lock what.

======================================================================

CONTEXT AND ASSUMPTIONS
======================================================================

1.1 System Context

LLMC runs locally on a single host.

llmc_mcp is an MCP server exposing tools to multiple clients:

LLMC TUI / CLI

Editor integrations

Local desktop agents

Remote MCP clients (over network tunnel or similar)

Multiple agents can act at the same time on:

Repo code and config files

LLMC RAG database (SQLite, WAL mode)

Knowledge graph JSON (enrichment metadata)

Generated docs under DOCS / REPODOCS

1.2 Key Assumptions

Single process model: all MCP tools are served from a single llmc_mcp process (multi-threaded or async).

SQLite is configured in WAL mode.

Existing docgen engine is available as a callable Python API.

Existing logging and metrics facilities exist and can accept structured events.

AGENTS.md and CONTRACTS.md define behavioral constraints (for example no random files in repo root) and must be respected.

======================================================================
2. FUNCTIONAL REQUIREMENTS

FR1: MAASL shall provide a single API to wrap stomp-prone operations:
call_with_stomp_guard(op, resources, intent, mode) -> Result.

FR2: Code write operations (write_file / refactor_file) shall:
- Serialize writes per file.
- Use atomic write semantics (temp file + rename).
- Fail fast when the file is locked beyond a configured timeout.

FR3: RAG DB write operations shall:
- Use SQLite BEGIN IMMEDIATE or a dedicated writer thread to serialize writes.
- Enforce bounded transaction duration.
- Report DB_BUSY style failures as MCP errors instead of hanging.

FR4: Knowledge graph / metadata updates shall:
- Perform deterministic merge of concurrent updates.
- Avoid blind overwrite of the graph JSON file.
- Log merge conflicts.

FR5: Docgen operations shall:
- Be idempotent based on source file hash (SHA header).
- Enforce a repo-level docgen mutex.
- Skip work when docs are already up to date.

FR6: MAASL shall expose MCP tools for introspection:
- llmc.locks : list currently held locks, with holders and durations.
- llmc.stomp_stats : aggregated counters and metrics.
- llmc.docgen_status : summary of recent docgen runs.

FR7: Lock acquisition shall:
- Support per-resource class wait timeouts.
- Distinguish interactive vs batch modes.

FR8: Errors shall be returned as structured MCP errors including:
- RESOURCE_BUSY
- DB_BUSY
- DOCGEN_BUSY
- STALE_VERSION
- INTERNAL_ERROR (fallback).

======================================================================
3. NON-FUNCTIONAL REQUIREMENTS

NFR1: Interactive operations should usually acquire locks within 500 ms.

NFR2: RAG DB write transactions should typically complete in less than 1000 ms.

NFR3: No operation shall hold a MAASL lock beyond a defined lease TTL (default 30 seconds) without renewal.

NFR4: MAASL must be thread safe if llmc_mcp uses threads, and safe for concurrent async tasks if using asyncio.

NFR5: Telemetry overhead should be small relative to operation cost (no heavy serialization or blocking IO in hot paths).

NFR6: Design must be incremental: it should be possible to enable only code + docgen protection first, then DB and graph later.

======================================================================
4. ARCHITECTURE OVERVIEW

4.1 Component List

MAASL facade (maasl.py)

Single entry point: call_with_stomp_guard.

PolicyRegistry

Configures resource classes and concurrency strategies.

LockManager

In-process locks, leases, fencing tokens.

DbTransactionManager

Helpers for SQLite writer sessions and transaction scopes.

MergeEngine

Deterministic merge for knowledge graph / metadata JSON.

DocgenCoordinator

Wrapper for docgen engine with SHA gating and repo-level mutex.

TelemetrySink

Structured log and metrics emission.

MCP Tool Shims

Thin wrappers for stomp-prone tools inside llmc_mcp.

4.2 Module Layout (proposed)

llmc_mcp/

init.py

maasl.py (MAASL facade, PolicyRegistry wiring)

locks.py (LockManager implementation)

db_guard.py (DbTransactionManager)

merge_meta.py (MergeEngine for graph / metadata)

docgen_guard.py (DocgenCoordinator)

telemetry.py (Telemetry helpers)

tools/

code_tools.py (write_file, refactor_file MCP tools)

rag_tools.py (rag_enrich, etc.)

docgen_tools.py (docgen_file, docgen_repo)

admin_tools.py (llmc.locks, llmc.stomp_stats, llmc.docgen_status)

4.3 Resource Classes

ResourceClass model:

name: string (CRIT_CODE, CRIT_DB, MERGE_META, IDEMP_DOCS).

concurrency: string (mutex, single_writer, merge, idempotent).

lock_scope: string (file, db, repo, graph).

lease_ttl_sec: int (default 30 for code, 60 for DB).

max_wait_ms: int (500 for interactive, 5000 for batch).

stomp_strategy: string (fail_closed, fail_open_merge).

Resource key scheme (examples):

Code file: "code:/absolute/path/to/foo.py"

DB writer: "db:rag"

Graph JSON: "graph:main"

Docgen repo: "docgen:repo"

======================================================================
5. DATA STRUCTURES

5.1 ResourceClass

Python dataclass (in maasl.py or a shared types module):

class ResourceClass:
name: str
concurrency: str # "mutex", "single_writer", "merge", "idempotent"
lock_scope: str # "file", "db", "repo", "graph"
lease_ttl_sec: int
max_wait_ms: int
stomp_strategy: str # "fail_closed", "fail_open_merge"

5.2 ResourceDescriptor

Captured per call by MCP tool shims:

class ResourceDescriptor:
resource_class: str # e.g. "CRIT_CODE"
identifier: str # e.g. absolute path or logical resource id

5.3 LockState

Managed by LockManager:

class LockState:
resource_key: str # "code:/path/to/foo.py"
mutex: threading.Lock or asyncio.Lock
holder_agent_id: str or None
holder_session_id: str or None
lease_expiry_ts: float # epoch seconds
fencing_token: int # monotonic increasing

5.4 DbWriteTask (for optional single-writer thread)

class DbWriteTask:
task_id: str
agent_id: str
description: str
func: Callable[[], None]
created_ts: float

5.5 GraphPatch

Represents a mergeable metadata update:

class GraphPatch:
nodes_to_add: list
edges_to_add: list
properties_to_set: dict # key -> value
properties_to_clear: list # keys

Details of node and edge schemas should reuse the existing graph structure.

5.6 DocgenResult

class DocgenResult:
status: str # "generated", "noop", "skipped", "error"
file: str
hash: str or None
duration_ms: int
error: str or None

======================================================================
6. MAASL FACADE DESIGN

6.1 Public API

Function:

def call_with_stomp_guard(
op: Callable[[], Any],
resources: list[ResourceDescriptor],
intent: str,
mode: str,
agent_id: str,
session_id: str,
) -> Any:

Parameters:

op: closure capturing the actual LLMC action.

resources: list of ResourceDescriptor objects.

intent: human readable label, e.g. "refactor_file", "rag_enrich".

mode: "interactive" or "batch".

agent_id: ID of the calling agent (from MCP metadata).

session_id: ID of the calling session (from MCP metadata or environment).

Return:

The return value of op() on success.

Raises MAASLError subclasses for known failure modes, to be translated to MCP errors at the tool layer.

6.2 High Level Flow

Resolve each ResourceDescriptor to a concrete ResourceClass (via PolicyRegistry).

Derive resource keys and lock parameters (ttl, max_wait, strategy).

Acquire locks in a deterministic order (sorted by resource_key).

For CRIT_DB resources, enter DbTransactionManager context.

For MERGE_META, capture op as a function that returns a GraphPatch or uses MergeEngine callback.

Execute op() within the protected section.

Commit DB transaction if any.

Apply merge for MERGE_META resources.

Release locks.

Emit telemetry for the operation (duration, contention, outcome).

6.3 Error Handling

If lock acquisition fails (timeout):

Raise ResourceBusyError with details (resource_key, holder_agent_id if known).

If DB transaction fails due to locking:

Raise DbBusyError.

If docgen indicates hash mismatch:

Raise DocgenStaleError.

All unexpected exceptions:

Wrap in MaaslInternalError with original exception details logged.

======================================================================
7. SUPPORTING COMPONENTS

7.1 PolicyRegistry

Responsibilities:

Define mapping from resource_class name to ResourceClass configuration.

Provide helper to map ResourceDescriptor to ResourceClass and compute:

resource_key

max_wait_ms (considering mode)

lease_ttl_sec

Implementation:

Static dictionary defined at module load time in maasl.py or policy.py.

Optional override from config file (llmc.toml) for advanced tuning.

7.2 LockManager

Responsibilities:

Maintain LockState per resource_key.

Provide:

acquire(resource_key, agent_id, session_id, lease_ttl_sec, max_wait_ms, mode) -> LockHandle
renew(resource_key, lease_ttl_sec) -> None
release(resource_key, agent_id, session_id, fencing_token) -> None
snapshot() -> list of LockState for introspection.

Behavior:

Acquisition:

Get or create LockState for resource_key.

Try non-blocking acquire on mutex.

If locked:

If current time < lease_expiry and max_wait_ms > 0:

Wait with short sleeps until available or timeout.

If lease expired:

Replace holder info with new agent, bump fencing_token, acquire mutex.

If timeout:

Raise ResourceBusyError.

Release:

Only allowed if fencing_token matches or if forced unlock logic is implemented for recovery.

7.3 DbTransactionManager

Responsibilities:

Provide a context manager for DB writes:

with db_writer_session(mode, intent, agent_id) as conn:
...

Behavior:

For simple mode:

Acquire CRIT_DB lock via LockManager at MAASL level.

Open a new SQLite connection with appropriate pragmas.

Execute "BEGIN IMMEDIATE".

Yield connection to caller.

On exit, COMMIT or ROLLBACK on exception.

For advanced single-writer thread mode (optional later):

Accept closures as DbWriteTask.

Execute tasks sequentially in a dedicated thread.

7.4 MergeEngine

Responsibilities:

Compute deterministic merged graph JSON from current_graph and a GraphPatch.

Ensure:

No duplicate node IDs.

No duplicate edges with same id or (src, dst, type) tuple if that is the schema.

LWW semantics for property updates with a deterministic tie breaker (for example timestamp or agent_id order).

API:

def apply_patch(current_graph: dict, patch: GraphPatch) -> dict

7.5 DocgenCoordinator

Responsibilities:

Enforce SHA gating and repo-level docgen mutex.

API:

def docgen_file(path: str, agent_id: str, session_id: str) -> DocgenResult

Behavior:

Compute SHA256 of source file.

Check existing doc file in DOCS / REPODOCS for SHA header.

If match, return DocgenResult(status="noop").

Acquire docgen:repo lock via LockManager.

Call existing docgen engine to generate markdown.

Validate that line 1 contains the expected SHA.

Perform atomic write of doc file.

Release lock.

Return DocgenResult(status="generated").

7.6 TelemetrySink

Responsibilities:

Provide convenience functions to log MAASL events:

log_lock_acquired(...)
log_lock_timeout(...)
log_db_write(...)
log_graph_merge(...)
log_docgen(...)

Implementation:

Use Python logging with JSON or key=value style.

Optionally integrate with MetricsCollector if present.

======================================================================
8. MCP TOOL INTEGRATION

8.1 Code Tools (write_file / refactor_file)

Pseudo-code for write_file tool:

def mcp_write_file(path: str, new_content: str, mode: str, ctx: ToolContext):
agent_id = ctx.agent_id
session_id = ctx.session_id
descriptor = ResourceDescriptor("CRIT_CODE", abs_path(path))

  def op():
      atomic_write(abs_path(path), new_content)
      return {"path": path}

  try:
      result = call_with_stomp_guard(
          op=op,
          resources=[descriptor],
          intent="write_file",
          mode=mode,
          agent_id=agent_id,
          session_id=session_id,
      )
      return result
  except ResourceBusyError as e:
      raise mcp_error("RESOURCE_BUSY", e.to_dict())
  ...


8.2 RAG Tools (rag_enrich)

Pseudo-code:

def mcp_rag_enrich(target: str, mode: str, ctx: ToolContext):
agent_id = ctx.agent_id
session_id = ctx.session_id
db_desc = ResourceDescriptor("CRIT_DB", "rag")
graph_desc = ResourceDescriptor("MERGE_META", "graph")

  def op():
      with db_writer_session(mode, "rag_enrich", agent_id) as conn:
          apply_rag_updates(conn, target)
      patch = build_graph_patch_for_target(target)
      return patch

  def wrapped_op():
      patch = op()
      # For MERGE_META, call_with_stomp_guard will know to apply patch
      return patch

  result = call_with_stomp_guard(
      op=wrapped_op,
      resources=[db_desc, graph_desc],
      intent="rag_enrich",
      mode=mode,
      agent_id=agent_id,
      session_id=session_id,
  )
  return result


8.3 Docgen Tools

Pseudo-code:

def mcp_docgen_file(path: str, mode: str, ctx: ToolContext):
agent_id = ctx.agent_id
session_id = ctx.session_id
code_desc = ResourceDescriptor("CRIT_CODE", abs_path(path))
docgen_desc = ResourceDescriptor("IDEMP_DOCS", "repo")
graph_desc = ResourceDescriptor("MERGE_META", "graph")

  def op():
      return DocgenCoordinator.docgen_file(abs_path(path), agent_id, session_id)

  result = call_with_stomp_guard(
      op=op,
      resources=[docgen_desc, code_desc, graph_desc],
      intent="docgen_file",
      mode=mode,
      agent_id=agent_id,
      session_id=session_id,
  )
  return result


8.4 Introspection Tools

llmc.locks

Reads LockManager.snapshot().

Returns list of current locks and basic fields.

llmc.stomp_stats

Reads aggregated counters from TelemetrySink or MetricsCollector.

llmc.docgen_status

Reads last N DocgenResult entries from a circular buffer in DocgenCoordinator.

======================================================================
9. ERROR MODEL AND MCP MAPPING

9.1 Internal Exceptions

ResourceBusyError

DbBusyError

DocgenStaleError

StaleVersionError

MaaslInternalError

9.2 MCP Error Mapping

RESOURCE_BUSY:

Causes: ResourceBusyError.

Payload: resource_key, holder_agent_id, holder_session_id, wait_ms, max_wait_ms.

DB_BUSY:

Causes: DbBusyError.

Payload: description, last_sqlite_error.

DOCGEN_BUSY:

Causes: ResourceBusyError for docgen:repo.

Payload: repo_id, current_holder.

DOCGEN_STALE:

Causes: DocgenStaleError.

Payload: file, expected_hash, got_hash.

STALE_VERSION:

Causes: StaleVersionError (when code version mismatch is detected).

Payload: file, expected_version, current_version.

INTERNAL_ERROR:

Causes: MaaslInternalError, any unhandled exception.

Payload: message, correlation_id for logs.

======================================================================
10. CONCURRENCY AND THREADING MODEL

LockManager relies on thread-safe data structures (e.g. a dict guarded by a global lock or concurrent map).

If llmc_mcp is async:

Use asyncio.Lock instead of threading.Lock where appropriate.

Acquisition logic must be compatible with event loop.

Locks are always acquired in sorted order by resource_key to reduce risk of deadlock.

Each MAASL call_with_stomp_guard call runs in the context of a single MCP tool invocation.

======================================================================
11. CONFIGURATION

Config keys (tentative, in llmc.toml):

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

Optional toggles for db_single_writer_mode and telemetry detail levels can also be defined.

======================================================================
12. TESTING STRATEGY

12.1 Unit Tests

LockManager tests:

Acquire and release behavior.

Lease expiry and takeover.

Fencing token increments.

Timeout behavior.

DbTransactionManager tests:

Successful write transaction.

Rollback on exception.

Simulated DB_BUSY case.

MergeEngine tests:

Merge of non-conflicting patches.

Conflict resolution determinism.

Property LWW semantics.

DocgenCoordinator tests:

NO-OP when hashes match.

Generated path on hash mismatch.

Hash mismatch protection (reject write if header wrong).

MAASL facade tests:

Single resource concurrency.

Multiple resources precedence and ordering.

Error propagation.

12.2 Integration Tests

Two simulated MCP agents attempting concurrent write_file on same file.

Assert only one write succeeds at a time, no corruption.

Concurrent rag_enrich calls updating RAG DB and graph.

Assert DB integrity and merged graph contains all expected nodes/edges.

Concurrent docgen_file calls on same file.

Assert only one docgen run occurs; others report NO-OP.

Introspection tools:

Acquire long-held locks in a test, then call llmc.locks and validate output.

12.3 Performance Tests

Measure lock acquisition latency under simulated concurrent load (N agents).

Ensure interactive operations stay within configured max_wait_ms under typical contention.

======================================================================
13. ROLLOUT PLAN

Phase 0: Telemetry only

Implement MAASL with no-op locking (or locks that do not block).

Wrap stomp-prone tools, emit telemetry about would-be locks.

Validate that basic behavior remains unchanged.

Phase 1: Code and docgen protection

Enable CRIT_CODE locks and atomic writes.

Enable docgen:repo mutex and SHA gate.

Roll out to local dev usage, verify no regressions.

Phase 2: RAG DB protection

Enable DbTransactionManager and CRIT_DB locks.

Monitor for DB_BUSY errors, adjust timeouts.

Phase 3: Graph merge

Enable MergeEngine and MERGE_META locking.

Monitor conflicts and graph invariants.

Phase 4: Leases and introspection

Enable lease TTL and fencing enforcement.

Expose llmc.locks, llmc.stomp_stats, llmc.docgen_status.

Document usage for operators and users.

End of SDD.