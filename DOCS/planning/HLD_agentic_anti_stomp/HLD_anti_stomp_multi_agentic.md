HLD — LLMC MCP Multi-Agent Anti-Stomp Layer

**Version:** v0.1 • **Date:** 2025-12-02  
**System:** LLMC + LLMC-MCP  
**Author:** LLMC

---

## 0. Executive Summary

LLMC is evolving from “one human + one agent” into a **multi-agent, multi-UI swarm** (TUIs, editors, background workers, remote MCP clients) all talking to the **same local LLMC instance and repo**.

This HLD defines a **Multi-Agent Anti-Stomp Layer** (MAASL) that sits in front of LLMC’s RAG/Docgen/File/DB subsystems and is accessed **through MCP**. Its job is to prevent “stomp conditions” — concurrent agents overwriting or corrupting each other’s work — **without killing responsiveness**.

The design reuses and formalizes the mechanisms already researched for LLMC:  

- **Per-resource stomp policy**: critical vs mergeable vs idempotent resources.  
- **File locks + atomic writes** for code / critical files.  
- **SQLite in WAL mode + BEGIN IMMEDIATE** with optional single-writer queue for the RAG DB.  
- **Mergeable JSON / graph updates** for metadata and knowledge graph.  
- **Content-hash (SHA) gates + repo-level mutex** for Docgen.  
- **Leases + basic fencing tokens** for robustness against hung agents.  
- **Telemetry + introspection tools** exposed via MCP (e.g. `llmc.locks`, `llmc.stomp_status`).  

MAASL is implemented as a **small coordination layer inside llmc_mcp** plus thin shims inside the core LLMC subsystems. MCP tools that can stomp (write / mutate / long-running) are routed through MAASL; pure reads bypass it.

This HLD is intentionally **host-local first** (single machine, many agents) but paves a direct path to a future distributed lock service if LLMC ever goes multi-host.

---

## 1. Goals & Non-Goals

### 1.1 Goals

1. **Prevent stomp conditions** across 5–15 concurrent LLMC agents on a single host:
   - No corrupted code files.
   - No inconsistent SQLite RAG DB.
   - Deterministic merges for JSON graph/docs.
2. **Expose stomp-aware behavior via MCP** so *any* MCP client (TUI, editor, desktop app) benefits automatically.
3. **Keep agents fast and interactive**:
   - Lock acquisition for interactive operations should usually complete in \< 500 ms.
   - Long-running background jobs should not block simple reads or quick writes more than necessary.
4. **Leverage existing LLMC capabilities**:
   - RAG DB (SQLite in WAL mode).  
   - `.llmc/rag_graph.json` (or equivalent knowledge graph).  
   - Docgen SHA headers and repo-level docgen mutex.  
   - Logging / metrics hooks.
5. Provide **clear observability** into stomp conditions and lock contention (who holds what, how long, how often busy).

### 1.2 Non-Goals

- Full **distributed** lock service across machines (future possible; not in this HLD).  
- Git-level concurrency / branching strategies. Git is assumed to be used *around* LLMC, not *inside* MAASL.  
- Fancy CRDT-based collaborative editing on code (too risky for syntax correctness). CRDT/merge is limited to **metadata and graph**.  

---

## 2. Context & Problem Statement

LLMC now has:

- A local **RAG daemon** with a SQLite store and JSON graph.  
- **Docgen** that writes markdown docs with SHA headers per source file.  
- Multiple user-facing frontends (CLI/TUI, editor plugins, soon MCP clients).  

We are introducing an **MCP server** (`llmc_mcp`) that exposes tools like:

- `rag_query`, `rag_search` (read).  
- `read_file`, (future) `write_file`, `refactor_file`.  
- `run_cmd` (with allowlist), `execute_code`.  
- `docgen_file`, `docgen_repo`.  

Without coordination, multiple MCP clients could:

- Simultaneously rewrite the same Python file.  
- Hammer the RAG DB with concurrent writes.  
- Generate stale docs for out-of-date code.  
- Race on JSON graph updates, losing metadata.

The **Preventing Stomp Conditions in Multi-Agent LLMC Orchestration** paper already designs primitives for file locks, SQLite concurrency, JSON merges, and docgen SHA idempotence. MAASL packages those into a **coherent, MCP-aware architecture** and defines how MCP tools must interact with them.

---

## 3. Architecture Overview

### 3.1 High-Level Diagram

```mermaid
flowchart LR
    subgraph Clients
      TUI["LLMC TUI / CLI"]
      Editor["Editor Plugin"]
      Desktop["Desktop App"]
      Remote["Remote MCP Client"]
    end

    subgraph MCP["llmc_mcp (MCP Server)"]
      Tools["MCP Tools<br/>rag_query / docgen / write_file / ..."]
      MAASL["MAASL<br/>Anti-Stomp Layer"]
      Policy["Resource Policy Registry"]
      Locks["Lock & Lease Manager"]
    end

    subgraph Core["LLMC Core"]
      Files["File Ops<br/>(code, docs)"]
      DB["RAG DB (SQLite WAL)"]
      Graph["Knowledge Graph JSON"]
      Docgen["Docgen Engine"]
      Logger["Telemetry & Logs"]
    end

    Clients -->|MCP requests| Tools
    Tools -->|stomp-aware calls| MAASL
    MAASL --> Policy
    MAASL --> Locks
    MAASL -->|safe ops| Files
    MAASL -->|safe ops| DB
    MAASL -->|merge ops| Graph
    MAASL -->|idempotent ops| Docgen
    MAASL --> Logger
3.2 Core Idea
MCP never touches shared state directly.
All MCP tools that mutate state call into MAASL with an explicit “resource set + stomp policy”.

MAASL:

Classifies each resource.

Acquires necessary locks or opens merge sessions.

Applies the correct concurrency control mechanism.

Emits telemetry about contention and stomp-avoidance.

Read-only tools (pure RAG queries, read_file, metadata introspection) bypass MAASL or use a read-only fast path that shares the same observability but no locking.

4. Resource Model & Stomp Policies
4.1 Resource Types
We classify LLMC resources into four main types:

Code Files (CRIT_CODE)

Example: *.py, *.sql, pipeline configs that must stay syntactically valid.

Stomp policy: Pessimistic per-file lock + atomic write, fail-closed on conflict.

RAG DB (CRIT_DB)

SQLite DB in WAL mode.

Stomp policy: Single writer at a time enforced via BEGIN IMMEDIATE and optional application-level write queue; short transactions only.

Knowledge Graph / Metadata (MERGE_META)

JSON graph, enrichment metadata, tags.

Stomp policy: Deterministic merges (CRDT-style sets for nodes/edges, LWW registers for fields), optional file-level lock only at final write.

Documentation (IDEMP_DOCS)

Generated markdown in DOCS/ / DOCS/REPODOCS/.

Stomp policy: SHA-gated idempotent generation + repo-level docgen mutex.

4.2 Resource Descriptor
MAASL keeps a registry in code (and optionally in config) defining each resource type:

python
Always show details

Copy code
@dataclass
class ResourceClass:
    name: str                # "CRIT_CODE", "CRIT_DB", ...
    concurrency: str         # "mutex", "single_writer", "merge", "idempotent"
    lock_scope: str          # "file", "db", "repo", "graph"
    lease_ttl_sec: int       # e.g. 30 for code, 60 for DB jobs
    max_wait_ms: int         # e.g. 500 for interactive, 5000 for batch
    stomp_strategy: str      # "fail_closed", "fail_open_merge"
MCP tools declare which resources they touch; MAASL uses the registry to choose behavior.

Examples:

write_file → resources=[("CRIT_CODE", "path/to/file.py")]

docgen_file → resources=[("IDEMP_DOCS", "path/to/file.py"), ("MERGE_META","graph")]

rag_enrich → resources=[("CRIT_DB", "rag.db"), ("MERGE_META","graph")]

5. Component Design
5.1 MCP Tool Shims
Each MCP tool that can stomp is implemented as a thin shim:

text
Always show details

Copy code
MCP Tool → MAASL.call_with_stomp_guard(op, resources, intent, mode)
Where:

op — a function/closure capturing the actual LLMC action (e.g. “write this new code to file X”).

resources — list of resource descriptors (class + identifier).

intent — descriptive string ("refactor_func", "docgen_file", "rag_enrich").

mode — "interactive" or "batch" to tune timeouts.

The shim does no direct IO; it delegates to MAASL for lock acquisition, DB transactions, merges, and telemetry.

5.2 MAASL Core
MAASL exposes a single main API:

python
Always show details

Copy code
def call_with_stomp_guard(op, resources, intent, mode) -> Result:
    """
    - Classify resources.
    - Acquire locks / leases as needed.
    - Open DB transaction if required.
    - Run op() inside the protected section.
    - Commit / merge / release locks.
    - Emit telemetry about timing, contention, and outcomes.
    """
Internally MAASL consists of:

Policy Registry — mapping resource class → concurrency strategy parameters.

Lock & Lease Manager — per-resource key mutexes with optional lease TTL and fencing token.

DB Transaction Manager — helper for BEGIN IMMEDIATE + commit/rollback with tuned timeouts.

Merge Engine — helper to apply deterministic merges on JSON graph / metadata.

Docgen Coordinator — wrapper around existing docgen implementation, enforcing SHA gates + repo mutex.

Telemetry Sink — writes structured events into LLMC’s logging / metrics system.

5.3 Lock & Lease Manager
Per resource key (e.g. "code:path/to/file.py", "db:rag", "graph:main", "docgen:repo"), MAASL maintains:

An in-process mutex (threading.Lock / asyncio.Lock).

Lease expiry time (now + ttl).

Fencing token (monotonic integer).

Acquisition logic:

Fast path: if mutex is free → acquire immediately, assign new fencing token.

Contended path:

If holder’s lease not expired → wait with backoff up to max_wait_ms.

If expired → log “lease expired” and allow takeover with new token.

If unable to acquire within max_wait_ms:

For interactive calls → fail fast with a clear MCP error (RESOURCE_BUSY).

For batch calls → optionally backoff and retry (configurable).

Leases and tokens mirror the patterns from the stomp research doc: time-bound locks and fencing prevent stale holders from acting after takeover.

5.4 DB Transaction Manager (RAG DB)
Each DB-mutating operation is funneled through:

python
Always show details

Copy code
with db_writer_session(timeout=mode_dependent_timeout):
    BEGIN IMMEDIATE;
    ... op() ...
    COMMIT;
Options:

Simple mode: each MAASL call opens its own connection and BEGIN IMMEDIATE transaction. SQLite’s internal locks serialize writers.

Advanced mode: a dedicated writer thread listens on an internal queue; MAASL enqueues write tasks, ensuring full serialization and zero SQLITE_BUSY in callers.

Both modes keep transactions short and honor a tuned timeout (e.g. 0.5–1s for interactive). If DB is locked beyond that, MAASL fails the operation with a clear DB_BUSY error rather than hanging.

5.5 Merge Engine (Knowledge Graph / Metadata)
For MERGE_META resources (graph JSON, doc metadata), MAASL supports two patterns:

Lock-read-merge-write (pessimistic)

Acquire a short-lived file lock on the JSON.

Load current graph.

Apply the change(s) from op() as a pure function (op returns a patch or delta).

Use deterministic merge rules (sets for nodes/edges, LWW for fields, sorted keys).

Write JSON atomically (temp file + rename).

Release lock.

Single-writer service (optional later)

MAASL forwards graph changes to an in-process “Graph Update Service” that owns the graph and writes it.

All MCP clients see a consistent serialized stream of updates.

In both cases, we never stomp another agent’s metadata: updates are merged, not overwritten, and conflicts are resolved deterministically.

5.6 Docgen Coordinator
Docgen is handled as a special IDEMP_DOCS resource with SHA gating:

MAASL docgen_file flow:

Compute SHA256 of source file.

Inspect existing doc file in DOCS/REPODOCS/ for SHA header.

If SHA matches → NO-OP, return DocgenResult(status="noop").

Acquire docgen:repo mutex (one docgen job per repo).

Call actual docgen engine with deterministic settings.

Verify the returned markdown’s first line SHA matches current file hash.

Write doc atomically.

Release mutex.

This reuses the content-addressed safeguards from the stomp research doc and ensures stale docgen can’t overwrite newer docs.

6. MCP Request Lifecycles
6.1 Example: write_file / Code Refactor
Use case: An MCP client requests a refactor on foo.py via a tool (llmc.write_file or llmc.refactor_file).

Flow:

MCP Tool Entry

Tool receives (path, new_content) plus agent_id, session_id, mode.

Declares resources=[("CRIT_CODE", path)].

Wraps the write logic into op() closure.

MAASL: Resource Resolution & Lock

Looks up CRIT_CODE policy: concurrency="mutex", scope="file", ttl=30s, max_wait=500ms, stomp_strategy="fail_closed".

Calls Lock Manager to acquire "code:path/to/foo.py" mutex + file lock (foo.py.lock).

If cannot acquire within 500ms → returns MCP error RESOURCE_BUSY(code_file_locked_by=agentX).

MAASL: Execution

Reads current foo.py.

Optionally verifies a precondition (e.g. ETag / SHA if the MCP client provided expected version).

Writes new_content to a temp file.

Atomically renames temp → foo.py.

Optionally runs a quick syntax check / formatter.

MAASL: Release & Telemetry

Releases file lock + mutex.

Emits telemetry: code_write event with hold time, wait time, and agent metadata.

MCP Response

Returns success + updated SHA/version to the client.

Result: two agents trying to write foo.py get serialized; nobody can corrupt the file or partially interleave writes.

6.2 Example: rag_enrich (DB + Graph)
Use case: MCP client triggers enrichment of a file, which updates SQLite and the JSON graph.

Flow (simplified):

Tool declares:
resources=[("CRIT_DB","rag.db"), ("MERGE_META","graph")].

MAASL acquires DB writer session + graph lock (graph lock purely for the write section).

Inside protected section:

Start BEGIN IMMEDIATE on the RAG DB.

Apply inserts/updates for spans / embeddings.

Commit.

Load graph JSON (under a file lock).

Merge new metadata nodes/edges.

Atomic write of updated JSON.

Release locks; emit telemetry for DB and graph parts separately.

Multiple enrich jobs queue politely, but reads (rag_query) stay free to run in parallel via WAL.

6.3 Example: docgen_file
Use case: Editor plugin asks MCP to generate docs for foo.py.

Flow:

Tool declares:
resources=[("IDEMP_DOCS","repo"), ("CRIT_CODE",path_for_read), ("MERGE_META","graph")].

MAASL computes SHA of foo.py, checks existing doc SHA.

If up-to-date → skip, respond NO-OP.

Acquire docgen:repo mutex + optional lease.

Invoke docgen engine with deterministic context from RAG + graph.

Verify output SHA header; atomic write.

Release mutex and log event.

If two docgen requests race, one takes the mutex; the other sees up-to-date SHA and does no work.

7. Telemetry & Observability
7.1 Events & Metrics
Each MAASL operation emits structured events, for example:

maasl.lock_acquired

fields: resource_key, agent_id, wait_ms, lease_ttl_sec, fencing_token.

maasl.lock_timeout

fields: resource_key, agent_id, wait_ms, max_wait_ms.

maasl.db_write

fields: duration_ms, retry_count, busy_encounters.

maasl.graph_merge

fields: nodes_added, edges_added, conflicts_resolved.

maasl.docgen

fields: status ("generated"/"noop"/"skipped"), file, hash, duration_ms.

Metrics derived from events:

Lock contention (per resource): number of waits, average wait, max wait.

Lock hold duration (per class).

Frequency of SQLITE_BUSY and DB timeouts.

Docgen NO-OP ratio (how often we skip redundant work).

Merge conflict rate (indicator of overlapping metadata work).

7.2 MCP Introspection Tools
Expose read-only MCP tools for debugging and UX:

llmc.locks – list current locks and their holders:

resource_key, agent_id, held_ms, lease_expiry.

llmc.stomp_stats – summarized metrics since process start.

llmc.docgen_status – last docgen runs and their outcomes.

These tools help users understand “why is this operation blocked?” without guessing.

7.3 User-Facing Messages
For interactive MCP clients, MAASL provides clear error classes:

RESOURCE_BUSY — another agent currently owns a lock; message includes who/what.

DB_BUSY — RAG DB contention beyond configured timeout.

DOCGEN_BUSY — docgen already running for repo.

STALE_VERSION — expected code/doc version mismatched; suggests re-fetch.

This avoids the “UI just feels laggy” problem; users know the system is intentionally preventing stomp.

8. Failure Modes & Recovery
8.1 Hung Agents
If an agent crashes, OS file locks / DB connections will generally be released; MAASL’s mutexes in-process release when the thread dies.

If an agent hangs (thread still alive but not making progress):

The lease TTL (e.g. 30s) for a resource will expire.

A new contender can take over and receive a higher fencing token.

Any subsequent operations from the stale holder that check the token will be rejected.

MAASL logs an alert: maasl.lease_expired with the stuck agent id.

For critical cases (e.g. DB writer stuck), an external watchdog could terminate the process.

8.2 SQLite Edge Cases
Long-running read transactions (should be rare) can delay WAL checkpoints; but they do not block writers in WAL mode.

Long-running write transactions are prevented by discipline: short, bounded operations only.

If DB is locked beyond configured timeout, MAASL returns DB_BUSY; no corruption occurs, only loss of that one write attempt.

8.3 Graph Merge Bugs
If merge code throws or detects invariant violations (e.g. duplicate IDs or dangling edges):

The operation is rolled back; JSON on disk is not modified.

MAASL logs a graph_merge_failure event with details.

The client receives a clear MCP error with hints to re-run or inspect logs.

8.4 Docgen Mismatch
If docgen engine returns markdown whose SHA header does not match the current file hash:

MAASL refuses to write the doc.

Logs an error (docgen_hash_mismatch).

Returns DOCGEN_STALE error to the client.

Next docgen attempt (with fresh context) should succeed.

9. Phased Implementation Plan
9.1 Phase 0 — Telemetry-First (No Behavior Change)
Add MAASL skeleton into llmc_mcp:

Policy registry with resource classes.

Lock manager API stub (acquire, release) that currently does nothing.

Wrap all potentially stompy MCP tools through call_with_stomp_guard, but initially no locking, only telemetry events.

Deploy and observe:

Which resources are frequently accessed concurrently.

Where contention would happen if we turned locks on.

Exit criteria: telemetry shows at least basic stomp patterns and confirms that routing through MAASL does not break anything.

9.2 Phase 1 — Code & Docgen Protection
Implement CRIT_CODE file locks + atomic writes:

.lock files per code file.

500ms max wait for interactive tools.

Turn on IDEMP_DOCS docgen coordinator:

SHA gates.

Repo-level docgen mutex.

Wire MCP tools write_file / refactor_file / docgen_file to use these.

Exit criteria: two concurrent refactors / docgens cannot corrupt files or docs; telemetry shows locks functioning; interactive latency acceptable.

9.3 Phase 2 — RAG DB Write Serialization
Implement DB Transaction Manager with BEGIN IMMEDIATE.

Optionally add single writer thread for heavy write scenarios.

Wrap all DB-mutating operations in MAASL DB sessions.

Tune timeouts and backoff; add DB_BUSY errors.

Exit criteria: no SQLITE_BUSY leaks to logs under normal load; writes are serialized and fast; read performance unaffected.

9.4 Phase 3 — Graph / Metadata Merge
Introduce Merge Engine for JSON graph.

Switch graph updates from “rewrite whole JSON” to “lock-read-merge-write”.

Add conflict logging and basic CRDT-style semantics for nodes/edges/properties.

Exit criteria: multiple concurrent enrichers can safely extend the graph; merge conflicts are handled deterministically and rarely cause errors.

9.5 Phase 4 — Leases, Fencing & Introspection
Turn on lease TTLs and fencing tokens for critical resources.

Implement llmc.locks and llmc.stomp_stats MCP tools.

Add deadlock / stuck-lock detection (e.g. warnings when locks held > 30s).

Exit criteria: hung or misbehaving agents can’t permanently block others; operators can see current lock state and stomp metrics easily.

9.6 Phase 5+ — Optional Distributed Evolution
Out of scope for this HLD, but this design maps cleanly to:

Replacing in-process Lock Manager with a small lock service (e.g. SQLite / Postgres / Redis based).

Sharing MAASL semantics across machines while preserving fencing and leases.

10. Summary
MAASL turns LLMC’s existing concurrency primitives (file locks, SQLite discipline, JSON merges, SHA-gated docgen) into a cohesive, MCP-visible anti-stomp architecture.

Key properties:

Safety: critical resources are protected by pessimistic locks and short transactions.

Liveness: metadata and docs use merge and idempotence, not blunt global locks.

Clarity: MCP clients get explicit, structured feedback when an operation is blocked or rejected.

Incremental: shipped in phases, starting with telemetry and the highest-value protections.

Once implemented, multiple LLMC agents — TUIs, editors, and remote MCP clients — can all operate on the same repo and RAG state without stepping on each other’s toes, while still feeling fast and responsive to the human in the loop.
"""

path = Path("/mnt/data/LLMC_MCP_MultiAgent_AntiStomp_HLD.md")
path.write_text(hld_content, encoding="utf-8")
path

Always show details

Copy code
Here’s the design in plain language first, then I’ll give you the .md download note.

TL;DR HLD shape
Name (working): LLMC MCP Multi-Agent Anti-Stomp Layer (MAASL)

Role:
Sits inside llmc_mcp and becomes the “traffic cop” for any MCP tool that can stomp on shared state:

Code files

RAG SQLite DB

Knowledge graph JSON / metadata

Docgen files in DOCS/REPODOCS/

It wraps MCP tools like:

write_file / refactors

rag_enrich / any RAG-DB mutating op

docgen_file / docgen_repo

future enrichers / indexers

…so that those tools never directly hit the repo / DB. They call:

python
Copy code
MAASL.call_with_stomp_guard(op, resources, intent, mode)
where resources is “here’s what I’m about to touch”, and MAASL decides:

What locks to take

What merge strategy to use

Whether to SHA-gate / idempotent-skip

How long to wait, and whether to fail fast
(esp. < 500 ms target for interactive flows Preventing Stomp Conditions in …)

Resource classes & strategies
We reuse your stomp paper’s taxonomy but wire it to MCP:

CRIT_CODE (code files)

Per-file mutex + .lock file (pessimistic).

Non-blocking acquire with ~500 ms cap for interactive.

Writes are temp-file + atomic rename so no half-written code ever hits disk. Preventing Stomp Conditions in …

CRIT_DB (RAG SQLite in WAL)

Writes go through a DB writer session using BEGIN IMMEDIATE, short transactions only. Preventing Stomp Conditions in …

Option A: let SQLite serialize writers via file locks.

Option B (later): single writer thread that consumes a queue of write tasks → zero SQLITE_BUSY seen by callers.

MERGE_META (knowledge graph / metadata JSON)

Graph updates represented as “patches”.

MAASL does lock-read-merge-write with deterministic rules:

sets for nodes/edges, LWW for fields, sorted keys, conflict logging. Preventing Stomp Conditions in …

Optional evolution: a single in-process “graph update service” with event/patch stream.

IDEMP_DOCS (generated docs)

Docgen is idempotent per content hash: docs carry SHA256: <source-hash> on line 1. Preventing Stomp Conditions in …

Repo-level mutex: only one docgen job per repo at a time.

Before generating:

If existing doc SHA == file SHA → NO-OP.

After generating: verify returned SHA header matches current file SHA; only then atomic-write.

Each MCP tool declares which resources it touches. Example mapping:

llmc.write_file → [("CRIT_CODE", path)]

llmc.rag_enrich → [("CRIT_DB","rag.db"), ("MERGE_META","graph")]

llmc.docgen_file → [("IDEMP_DOCS","repo"), ("CRIT_CODE",path), ("MERGE_META","graph")]

Locking / leases / fencing
Inside llmc_mcp you get a tiny Lock & Lease Manager:

Keyed by resource: code:foo.py, db:rag, graph:main, docgen:repo

Maintains:

in-process mutex

lease_expiry (e.g. now+30s)

fencing_token (monotonic int) Preventing Stomp Conditions in …

Behavior:

Try to grab mutex non-blocking; if held:

If lease still valid → backoff/retry up to max_wait_ms.

If lease expired → log and steal lock; bump fencing token.

If cannot acquire before max_wait_ms:

interactive: return RESOURCE_BUSY error with who/what holds it.

batch: configurable retry/backoff.

For operations that care (DB writes, graph writes, maybe docgen), MAASL can compare the current fencing token before committing to catch truly stale actors in edge cases.

MCP flows (how it feels from clients)
1) write_file / refactor

MCP tool wraps the action:

python
Copy code
MAASL.call_with_stomp_guard(
    op=lambda: atomic_write(path, new_content),
    resources=[("CRIT_CODE", path)],
    intent="refactor",
    mode="interactive",
)
MAASL:

acquires code:path lock + .lock file

does read / temp-write / rename

releases and logs

If another agent tries to stomp, it either:

Queues briefly and runs after the first one, or

Gets RESOURCE_BUSY(code_file_locked_by=agent123) within ~500 ms.

2) rag_enrich

MAASL grabs db:rag writer session + graph:main lock (for write phase only).

Runs BEGIN IMMEDIATE, writes, commits.

Loads JSON graph, applies patch via Merge Engine, atomic-writes.

Releases resources.

Multiple enrichers are serialized at the “change commit” level but can still stream / compute stuff in parallel before the commit.

3) docgen_file

SHA gate first; if already up-to-date, skip.

Else, MAASL grabs docgen:repo mutex.

Calls existing docgen pipeline, verifying SHA header before writing. Preventing Stomp Conditions in …

On races, only one actually does the expensive work; others see up-to-date docs and NO-OP.

Telemetry & MCP introspection
MAASL emits structured events:

maasl.lock_acquired, maasl.lock_timeout, maasl.db_write, maasl.graph_merge, maasl.docgen

plus metrics: wait times, hold times, busy counts, merge conflicts, docgen NO-OP ratio, etc.

You can surface this through MCP tools:

llmc.locks → list current locks, who holds them, how long.

llmc.stomp_stats → aggregated stomp-related metrics.

llmc.docgen_status → last N docgen runs and results.

That gives you the “why is this stuck?” answer without spelunking logs.

Phasing (how you’d actually ship it)
Phase 0 — Telemetry first, no behavior change

Wrap potentially stompy MCP tools in call_with_stomp_guard, but lock manager is a no-op; just log “would have locked X”.

Use this to see real contention patterns before turning on any brakes.

Phase 1 — Guard code & docgen

Turn on CRIT_CODE file locks + atomic writes.

Turn on docgen SHA gate + repo mutex (if not already consistently enforced).

Wire write_file / refactor_file / docgen_file to MAASL.

Phase 2 — Guard RAG DB

Implement DB writer sessions (BEGIN IMMEDIATE, short tx, tuned timeouts).

Optionally single writer thread if you see SQLITE_BUSY in practice.

Phase 3 — Graph / metadata merge

Switch graph updates to lock-read-merge-write using deterministic rules.

Start logging merge conflicts and verifying invariants.

Phase 4 — Leases, fencing, introspection tools

Enable lease TTL and fencing tokens for critical resources.

Add llmc.locks / llmc.stomp_stats tools.

Add alerts when locks held > 30s, etc.

After that, you’re in “nice to have” territory (distributed lock service, etc.).