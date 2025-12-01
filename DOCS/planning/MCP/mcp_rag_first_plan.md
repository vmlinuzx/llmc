
# LLMC MCP — Streamlined *RAG‑First* Build Plan (TE later)
*Updated: 2025-12-01T17:45:38*

**Thesis:** Ship a **minimal MCP that “just works” with RAG** and no fancy wrappers. TE moves *after* we prove stable, fresh-first orchestration.

---

## Scope (now)
- MCP server with **zero client pre-prompts**.
- **Fresh-only** RAG injection (no caching, no anti-stomp infra).
- Minimal tool set: `read_file(range)`, `list_dir`, `stat`, `run_cmd(lite)` (guarded).
- **Envelope-lite** formatter + **handle** service for big outputs.
- Metrics (tokens/latency/errors), policy/ACL, benchmark vs Desktop Commander.

## Out of Scope (defer)
- TE wrappers (rg/grep/cat enrichers), semantic caching, anti-stomp coordination, dynamic tool filtering, differential prompts.

---

## Milestones (tiny PRs)

### M0 — Skeleton
- FastAPI service: `/invoke_agent`, `/tool`, `/handles/get`, `/health`.
- In-memory sessions + handles.
- **Flag:** `mcp.enabled=true`.
- **DoD:** Docker build; 100 req/min soak; p95 < 10ms (no-op).

### M1 — Minimal Tool Registry + Lazy Docs
- One-line signatures; inject-once per session on first use.
- **Flag:** `mcp.lazy_docs=true`.
- **DoD:** first-use token bump < 80 tokens; then zero.

### M2 — RAG Pre‑Call Injection (fresh-only)
- Adapter: `rag.search(q, scope, k, budget_tokens)` → snippets+provenance.
- Strict budgets: `k≤3`, `budget_tokens≤600`.
- **Flag:** `mcp.jit_context=true`.
- **DoD:** provenance mandatory; truncation safe; unit tests for scoping.

### M3 — Envelope‑Lite + Handles
- Replace large tool outputs with compact envelopes (counts, truncated preview, `handle=<id>`).
- `handles.get(id)` re-validates `mtime/hash` (stale → instruct re-run).
- **Flags:** `mcp.envelopes=true`, `mcp.handles=true`.
- **DoD:** 10k‑line reads ≤ 200 tokens + handle; stable formatting.

### M4 — Metrics + Cost Telemetry
- Tokens in/out per turn; latency; error codes; `/metrics` and CSV artifacts.
- **Flag:** `mcp.metrics=true`.
- **DoD:** Grafana-ready; CI parses CSV; “token/answer” panel.

### M5 — Policy/ACL + Sandbox
- Per-tool allowlists; path constraints; redaction hooks.
- **Flag:** `mcp.policy=true`.
- **DoD:** denial paths tested; audit logs deterministic.

### M6 — Benchmark Harness (vs Desktop Commander)
- Repro workloads; side-by-side tokens/latency.
- **DoD:** ≥ 40% token reduction vs DC baseline; artifacts under `benchmarks/`.

> **Later (separate epics):** TE v1 (rg/grep/cat), semantic caching (snapshot-safe only), anti-stomp, dynamic tool filtering, differential prompts.

---

## Interfaces (stable)

### 1) Invoke
`POST /invoke_agent`
```json
{ "session_id": "S", "role": "Otto|Beatrice|Rem|Grace", "user_msg": "text", "inject_context": "" }
```
**Response:** `{ "text": "..." }` (real impl calls the model)

### 2) Tool
`POST /tool`
```json
{ "session_id": "S", "name": "read_file", "args": { "path": "X", "offset": 0, "length": 200 } }
```
**Response:** `{ "enriched_markdown": "...", "handle": "H?" }`

### 3) Handle
`POST /handles/get`
```json
{ "id": "H" }
```
**Response:** chunk for expansion, after `mtime/hash` re-validate.

### 4) RAG Adapter (internal)
```ts
get_context(q: string, scope: "repo"|"docs"|"both", k=3, budget_tokens=600) -> [{text, src, score}]
```

---

## Prompt Injection Shape (example)
```
[CTX.RAG scope=repo k=3 budget≤600]
- S1: text  (src=path#Lx-Ly, score=0.82)
- S2: text  (src=path#Lx-Ly, score=0.77)
- S3: text  (src=path#Lx-Ly, score=0.74)
[END]

[TOOLS DOCS, once-per-session]
- read_file(path, offset=0, length=200) → preview or handle
- list_dir(path) → names
- stat(path) → size, mtime, hash?
```

---

## Acceptance Gates
- **A (M0–M3):** E2E “small prompt → JIT RAG snippet → single tool call → envelope + handle → expansion (fresh).”  
  - Token overhead from MCP < **1%** of injected RAG.  
  - Staleness guard works.
- **B (M4–M6):** Telemetry on; policy enforced; ≥ **40%** tokens saved vs DC baseline.

---

## CI & Tests (starter set)
- Unit: prompt budgeter, snippet provenance, envelope formatter, handle re-validate.
- API smoke: 200s + errors; JSON schema checks.
- Perf: p95 < 100ms for handle fetch, < 10ms no-op calls.
- Token audit: record request/response deltas; CSV under `artifacts/`.

---

## Risks & Mitigations
- **RAG scope drift** → enforce budget and scope; fail safe to smaller k.
- **Staleness** → require `mtime/hash` on expansion; reject stale handles.
- **Prompt creep** → keep tool docs ≤ 160 chars; inject once; turn off by flag if needed.

---

## Next Patch (recommended)
**M0 + M1** in one PR: skeleton + minimal tool registry + inject-once docs, with tests + Dockerfile.  
Then **M2** (JIT RAG) as its own PR.
