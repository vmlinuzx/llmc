
# Software Design Document — LLMC MCP (MVP, RAG‑First)
**Version:** v0.3 • **Date:** 2025-12-01 22:00:00 • **Owner:** LLMC  
**Status:** M0-M4 Complete, M5 Fully Designed • **Target Milestones:** M0–M6

---

## 0. Executive Summary
Build a **minimal Model Context Protocol (MCP) server** that “just works” with LLMC’s RAG system, **without** pre‑prompt bloat or TE wrappers. Direct exposure is allowed for MVP, secured with a **static bearer token**. All behavior is **config‑driven** from `llmc.toml` so nothing is hard‑coded.

**Out of scope (MVP):** hairpin relay, TE wrappers, envelopes/handles, semantic caching, policy/ACL enforcement, anti‑stomp, dynamic tool filtering, differential prompting. These are roadmap items.

---

## 1. Goals & Non‑Goals
### 1.1 Goals
- G1. Provide a tiny, reliable MCP that exposes a **small tool surface** and a **RAG bootloader**.
- G2. **Token‑efficient** orchestration: no pre‑prompt boilerplate; server‑side RAG injection only.
- G3. **Configuration‑first:** everything lives under **MCP CONFIGURATION** in `llmc.toml`, with ENV/CLI overrides.
- G4. **Observability** behind a flag (metrics/logging/token audit), disabled/enabled via config.
- G5. **Direct exposure** by default; hairpin relay designed but deferred.

### 1.2 Non‑Goals (MVP)
- N1. No envelopes/handles or staleness re‑validation.
- N2. No fine‑grained policy/ACL enforcement (only coarse tool toggles/roots).
- N3. No semantic caching at MCP layer (LLMC owns freshness).
- N4. No TE wrappers (rg/grep/cat) or dynamic tool filtering.
- N5. No anti‑stomp session coordination.

---

## 2. Assumptions & Constraints
- A1. **Network:** Direct exposure on home IP with local domain; reverse proxy is optional.
- A2. **Auth:** Single static bearer token header `X-LLMC-Token` (no rotation).
- A3. **Tools:** Full filesystem `/` and `run_cmd` **enabled** (operator accepts risk).
- A4. **RAG:** Thin adapter that conforms to **AGENTS.md**/**CONTRACTS.md** conventions; no caching.
- A5. **Data egress:** Allowed (Desktop Commander–style) for MVP.
- A6. **Config precedence:** CLI → ENV → TOML → defaults.

---

## 3. Requirements
### 3.1 Functional Requirements (FR)
- **FR‑1:** Expose endpoints: `/health`, `/invoke_agent`, `/tool`, `/rag/search`, `/rag/bootload`.
- **FR‑2:** Validate static bearer token when `mcp.auth.mode="token"`.
- **FR‑3:** Tools: `read_file`, `list_dir`, `stat`, `run_cmd` (allowlist binaries).
- **FR‑4:** RAG adapter: `rag.search(q, scope, k, budget_tokens)` and `rag.bootload(session_id, task_id)`; return snippets with provenance.
- **FR‑5:** Respect timeouts/limits from config.
- **FR‑6:** Observability toggles: metrics/logging/token audit per config.
- **FR‑7:** Return standard error envelope with `correlation_id`.

### 3.2 Non‑Functional Requirements (NFR)
- **NFR‑1 (Performance):** No‑op p95 ≤ 15ms; tool call p95 ≤ 150ms; RAG search p95 ≤ 200ms (delegated).
- **NFR‑2 (Reliability):** Survive 10 r/s sustained with burst 20; graceful 429 when throttled.
- **NFR‑3 (Security):** Path normalization, traversal protection, arg validation, allowlisted `run_cmd` binaries.
- **NFR‑4 (Config):** Startup logs print effective config (minus secrets).
- **NFR‑5 (Portability):** Dockerized; optional reverse proxy sample.
- **NFR‑6 (Token Efficiency):** No tool docs injected; no pre‑prompt bloat; server sends only requested results.

---

## 4. Architecture & Components
```
Client (Claude/ChatGPT Tools)
   │  HTTP (token)
   ▼
MCP Core (FastAPI)
   ├─ Auth Middleware (token)
   ├─ Rate/Concurrency Gates
   ├─ Tool Adapter ──> FS/OS (read_file/list_dir/stat/run_cmd)
   ├─ RAG Adapter  ──> LLMC RAG APIs (search/bootload)
   └─ Observability (metrics/logs/token audit)
```

**Modules**
- **api.http**: FastAPI app, routers, middleware, error mapping.
- **auth.token**: header extraction, constant‑time compare, failure paths.
- **tools.fs/exec**: implementations for `read_file`, `list_dir`, `stat`, `run_cmd` with normalization and allowlists.
- **rag.adapter**: thin client to LLMC RAG + bootloader.
- **limits.gates**: request/response size caps, rate limits, concurrency caps.
- **config.loader**: merge defaults/TOML/ENV/CLI; provide `McpConfig` dataclass.
- **obs.telemetry**: Prometheus metrics, JSON logs, optional CSV token audit.

---

## 5. API Design (v0)
### 5.1 Conventions
- **Auth header:** `X-LLMC-Token: <secret>` when enabled.
- **Content‑Type:** `application/json; charset=utf-8`.
- **Error envelope:**
  ```json
  {
    "code": "ERR_CODE",
    "message": "human message",
    "hint": "optional",
    "correlation_id": "uuid"
  }
  ```

### 5.2 `GET /health`
- **200** body: `{"ok":true,"version":"v0"}`

### 5.3 `POST /invoke_agent`
- **Request:**
  ```json
  {
    "session_id": "S",
    "role": "Beatrice|Otto|Rem|Grace",
    "user_msg": "text",
    "inject_context": ""
  }
  ```
- **Response (MVP):**
  ```json
  {
    "text": "[MCP v0] received; use /rag/search for pre-call context"
  }
  ```
- **Notes:** This endpoint is primarily a pass‑through proof for MVP; real model invocation happens outside MCP.

### 5.4 `POST /tool`
- **Request:**
  ```json
  {
    "session_id":"S",
    "name":"read_file|list_dir|stat|run_cmd",
    "args": {}
  }
  ```
- **Responses:**
  - `read_file`: `{"data":"<raw_text>","meta":{"path": "...", "length": N}}`
  - `list_dir`: `{"data":["a","b"],"meta":{"path":"..."}}`
  - `stat`: `{"data":{"size":N,"mtime":TS,"mode":"0644","type":"file"}}`
  - `run_cmd`: `{"data":{"stdout":"...","stderr":"...","exit_code":0}}`
- **Validation:** normalize path; ensure within `allowed_roots`; `run_cmd` binary in allowlist.

### 5.5 `POST /rag/search`
- **Request:**
  ```json
  {
    "q":"...",
    "scope":"repo|docs|both",
    "k":3,
    "budget_tokens":600
  }
  ```
- **Response:**
  ```json
  {
    "snippets":[
      {"text":"...", "src":"path#Lx-Ly", "score":0.82},
      {"text":"...", "src":"path#Lx-Ly", "score":0.77}
    ],
    "provenance": true
  }
  ```
- **Notes:** Budget/scoping enforcement happens in adapter; truncation is allowed.

### 5.6 `POST /rag/bootload`
- **Request:** `{"session_id":"S","task_id":"T"}`
- **Response:** minimal `{"plan":"...","scope":"repo|docs|both","notes":"..."}` based on AGENTS/CONTRACTS.

### 5.7 Status Codes
- `200` OK, `400/422` validation, `401` unauthorized, `403` forbidden,  
  `413` too large, `429` rate limited, `500` internal.

---

## 6. Configuration (authoritative)
All keys live in `llmc.toml` under **MCP CONFIGURATION** (see full spec provided separately). Key MVP fields:

```toml
[mcp]
enabled = true
config_version = "v0"

[mcp.server]
host = "127.0.0.1"
port = 8080
tls_enabled = false

[mcp.auth]
mode = "token"
header = "X-LLMC-Token"
token_env = "LLMC_MCP_TOKEN"
allow_unauthenticated = false

[mcp.tools]
enable_run_cmd = true
allowed_roots = ["/"]
allow_outbound_network = true
run_cmd_allowlist = ["bash","sh","rg","grep","cat","ls","python","pip"]
exec_timeout = 30
read_timeout = 10
idle_timeout = 60

[mcp.rag]
jit_context_enabled = true
default_scope = "repo"
top_k = 3
token_budget = 600

[mcp.observability]
enabled = true
metrics_prometheus_enabled = true
metrics_path = "/metrics"
csv_token_audit_enabled = false
csv_path = "./artifacts/token_audit.csv"
log_format = "json"
log_level = "info"
retention_days = 0
include_correlation_id = true

[mcp.limits]
rate_limit_rps = 10
rate_limit_burst = 20
concurrency_per_token = 8
max_request_bytes = 262144
max_header_bytes  = 16384
```

**Precedence:** CLI overrides ENV → TOML → defaults. On startup, print effective config (minus secrets).

---

## 7. Security Design (MVP posture)
- **Auth:** Single static token in header; constant‑time compare.
- **Paths:** Normalize; reject traversal (`..`), symlink escape, or device files.
- **Run Cmd:** Allowlist binaries only; fixed arg parsing; timeouts; capture stdout/stderr; return exit code.
- **Outbound:** Allowed (per operator choice in MVP).
- **Reverse proxy:** Optional for TLS/rate‑limiting; not required on trusted LAN.

**Threats addressed:** port scans (token required), path traversal, command injection (allowlist + parsing), oversize payloads (limits), basic DoS (rate + concurrency caps).

---

## 8. Observability
- **Metrics (if enabled):** HTTP latency histograms (`p50/p95/p99`), error counts, auth failures, rate‑limit drops, tokens in/out.
- **Logs:** JSON with `correlation_id` (generate if missing), route, status, latency, token in/out (if audit on).
- **CSV token audit:** Append per‑turn deltas to `csv_path` when enabled.

---

## 9. Algorithms & Flows
### 9.1 Tool Call Flow (`/tool`)
```
Auth → rate gate → validate {name,args}
  → if name in {read_file,list_dir,stat}:
       normalize path, check roots, exec, return data/meta
    elif name == run_cmd:
       check allowlist, parse args, exec with timeout
       return stdout/stderr/exit_code
    else 422
→ log + metrics
```

### 9.2 RAG Search Flow (`/rag/search`)
```
Auth → rate gate → validate {q,scope,k,budget}
  → call LLMC RAG adapter with scope/budget
  → enforce k≤top_k and budget ≤ token_budget
  → return snippets + provenance
→ log + metrics
```

---

## 10. Data Structures
- **McpConfig** (dataclass): mirrors `llmc.toml` keys.
- **ToolRequest**: `session_id:str, name:str, args:dict`
- **ToolResponse**: `data:any, meta:dict`
- **RagSearchRequest**: `q:str, scope:str, k:int, budget_tokens:int`
- **RagSearchResponse**: `snippets:list[{"text","src","score"}] , provenance:bool`

---

## 11. Error Handling
- Map exceptions to error envelope codes:
  - `AUTH_FAILED` (401), `FORBIDDEN` (403), `BAD_ARGS` (422), `TOO_LARGE` (413),
    `RATE_LIMITED` (429), `INTERNAL` (500).
- Always include `correlation_id` in response and logs.

---

## 12. Testing Strategy
**Unit:** config parsing/precedence, token auth, path normalization, arg validation, run_cmd allowlist/timeout.  
**Integration:** E2E routes with happy/sad paths; RAG adapter smoke with fake server.  
**Perf:** k6 or locust scripts: p95 latencies within budgets; verify rate‑limit 429 behavior.  
**Security:** path traversal & symlink escape; command injection attempts; oversize bodies.  
**Benchmarks:** scripted tasks vs Desktop Commander; target **≥ 40%** token reduction due to no pre‑prompt and RAG‑first.

---

## 13. Deployment & Ops
- **Dockerfile** (non‑root user). `LLMC_MCP_TOKEN` must be present when auth is on.
- Optional **docker‑compose**: bind `host:port` per config.
- Optional **reverse proxy** (Caddy/Nginx) sample under `/deploy/`.
- Logs to stdout; metrics on `/metrics` when enabled.

---

## 14. Rollout Plan & Feature Flags
- Milestones:
  - **M0:** Skeleton (API + health + config loader + token auth). ✅
  - **M1:** Tool registry + fs/exec handlers. ✅
  - **M2:** RAG bootloader endpoints. ✅
  - **M3:** Limits & timeouts; run_cmd allowlist & parsing. ✅
  - **M4:** Observability flags (metrics/logging/token audit). ✅
  - **M5:** Docker/compose + TE integration.
  - **M6:** Benchmarks + HLD/SDD validation.
- Flags (in `llmc.toml`): `mcp.enabled`, `mcp.tools.enable_run_cmd`, `mcp.observability.enabled`, etc.

---

## 14.1 M4 Implementation Notes (Complete)

**Delivered 2025-12-01:**
- `McpObservabilityConfig` dataclass with TOML/ENV loading
- `observability.py` module (340 lines):
  - `generate_correlation_id()` - 8-char UUID prefix
  - `JsonLogFormatter` - structured JSON logs with cid, tool, latency_ms
  - `MetricsCollector` - thread-safe in-memory counters/histograms
  - `TokenAuditWriter` - CSV append trail
  - `ObservabilityContext` - unified facade
  - `setup_logging()` - JSON/text formatter based on config
- Server integration: all tool calls wrapped with timing, correlation IDs
- New tool: `get_metrics` - returns current stats (requires restart to appear)
- Tests: 19 new tests (42 total across all modules)

**Config added to `llmc.toml`:**
```toml
[mcp.observability]
enabled = true
log_format = "json"
log_level = "info"
include_correlation_id = true
metrics_enabled = true
csv_token_audit_enabled = false
csv_path = "./artifacts/mcp_token_audit.csv"
```

---

## 14.2 M5 Design: Docker + Tool Envelope Integration

### 14.2.1 Architecture Decision: No Transport Layer

**Decision:** Direct subprocess calls within the same container. No HTTP, no stdio gymnastics.

**Rationale:**
- MCP server is Python, TE is Python - same runtime
- TE exists at `scripts/te` as a CLI entry point
- subprocess.run() is simpler than socket/pipe management
- Fewer failure modes, trivial to debug
- HTTP only needed when TE becomes a separate daemon (M6+)

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  Docker Container                                           │
│                                                             │
│  MCP Server (Python, stdio transport to Claude Desktop)     │
│      │                                                      │
│      ├── health, rag_search, read_file, list_dir, stat     │
│      │                                                      │
│      └── run_cmd ─────────────────────┐                    │
│              │                         │                    │
│              ▼                         ▼                    │
│      MCP Allowlist Check        TE subprocess.run()        │
│      (security gate)            (enrichment layer)          │
│              │                         │                    │
│              └─────────┬───────────────┘                    │
│                        ▼                                    │
│              Shell execution (bash)                         │
│                        │                                    │
│                        ▼                                    │
│              TE Telemetry (SQLite)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 14.2.2 Security Model: Dual-Layer Allowlist

**Decision:** MCP allowlist is authoritative. TE trusts its caller.

| Layer | Responsibility | Enforcement |
|-------|---------------|-------------|
| MCP | Which binaries can run at all | `run_cmd_allowlist` in config |
| TE | Enrichment, budgets, telemetry | Passthrough for unknown commands |

**Flow:**
1. Agent calls `run_cmd(command="rg pattern .")` 
2. MCP checks: is `rg` in allowlist? → Yes, proceed
3. MCP calls TE via subprocess with `TE_AGENT_ID` env var
4. TE enriches if known (grep/cat/find), else passthrough
5. TE logs telemetry regardless
6. MCP receives output, records metrics, returns to agent

**Why MCP is authority:**
- MCP is the trust boundary (authenticated, rate-limited)
- TE is a library/tool, not a security perimeter
- Keeps TE simple - it enriches, it doesn't police

### 14.2.3 Agent & Session Identification

**Decision:** Explicit metadata passed via environment variables. Never inferred.

**MCP Session Context (internal struct):**
```python
@dataclass
class McpSessionContext:
    agent_id: str       # e.g., "claude-desktop-mcp"
    session_id: str     # e.g., "sess_2025-12-01T22-15-03"
    model: str          # e.g., "claude-3.7-sonnet"
    budget_profile: str # e.g., "M5-debug"
```

**Environment variables passed to TE:**
- `TE_AGENT_ID` - identifies the calling agent
- `TE_SESSION_ID` - identifies the conversation/task session
- `TE_MODEL` - model making the call (for analytics)

**Why not infer from budget:**
- Budget is a routing/config concern at MCP/orchestrator layer
- TE just logs: "call from agent X, session Y, model Z, running command C"
- Analytics (cost by milestone, agent comparison) consumes TE + MCP logs separately
- Keeps TE simple and decoupled

**Sources for session context:**
1. MCP transport metadata (if Claude Desktop provides it)
2. Config defaults: `mcp.session.default_agent_id`, etc.
3. Tool arguments (override for specific calls)

### 14.2.4 M5 Tool Surface

**Decision:** Named semantic tools, not generic `run_cmd`. Each tool calls TE internally.

**M5 Tools:**

| Tool | Description | TE Usage |
|------|-------------|----------|
| `te_run` | Execute arbitrary command through TE | Direct subprocess to `scripts/te` |
| `repo_read` | Read file with path security | TE passthrough or direct (config) |
| `repo_write_patch` | Apply patch/edit to file | Future - requires write_file research |
| `run_pytest` | Execute pytest with output parsing | `te pytest ...` with enrichment |
| `rag_query` | Search RAG index | Direct to RAG daemon (no TE) |

**Why named tools vs generic `run_cmd`:**
- Model sees semantic intent: "run tests" not "run arbitrary shell command"
- Each tool can have tailored validation and output parsing
- Easier to audit: "agent called run_pytest 5 times" vs "agent ran 5 commands"
- Matches Anthropic's "MCP as filesystem of tools, code as orchestrator" pattern

**Tool implementation pattern:**
```python
async def handle_te_run(args: dict, session: McpSessionContext) -> ToolResponse:
    """Execute command through Tool Envelope."""
    command = args["command"]
    
    # MCP-level allowlist check (security gate)
    if not is_allowed(command, config.tools.run_cmd_allowlist):
        return error("Command not in allowlist")
    
    # Build TE environment
    env = os.environ.copy()
    env["TE_AGENT_ID"] = session.agent_id
    env["TE_SESSION_ID"] = session.session_id
    env["TE_MODEL"] = session.model
    
    # Call TE via subprocess
    result = subprocess.run(
        [str(te_script), command],
        env=env,
        capture_output=True,
        timeout=config.te.timeout,
    )
    
    return parse_te_output(result)
```

**TE is invisible to model:** The model calls `te_run`, not `te`. TE is an implementation detail.

### 14.2.5 MCP Resources (Sidecars)

**Decision:** Load minimal context docs as MCP resources, not injected prompts.

**Resources to expose:**
- `agents.core.min.md` - Agent behavior contracts (minimal version)
- `contracts.env.min.md` - Environment/capability contracts (minimal version)

**Why resources not prompt injection:**
- Model requests what it needs
- Token-efficient: not loaded unless referenced
- Matches MCP resource pattern
- Sidecars can be updated without changing server code

**Resource implementation:**
```python
@server.list_resources()
async def list_resources():
    return [
        Resource(uri="llmc://docs/agents.core.min.md", name="Agent Contracts"),
        Resource(uri="llmc://docs/contracts.env.min.md", name="Environment Contracts"),
    ]

@server.read_resource()
async def read_resource(uri: str):
    if uri == "llmc://docs/agents.core.min.md":
        return load_file("DOCS/agents.core.min.md")
    # ...
```

### 14.2.6 TE Output Contract

**Current state:** TE outputs human-readable text with optional handle storage.

**Required for MCP integration:** Structured JSON response mode.

**Proposed `--json` flag for TE:**
```bash
te --json grep "pattern" path/
```

**Response schema:**
```json
{
  "success": true,
  "mode": "enriched|passthrough|raw",
  "command": "grep pattern path/",
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0,
  "enrichment": {
    "match_count": 42,
    "truncated": false,
    "handle": "res_01H...",
    "tokens_estimate": 1500
  },
  "telemetry": {
    "latency_ms": 45.2,
    "agent_id": "claude-dc",
    "budget_remaining": 178500
  }
}
```

**Fallback:** If `--json` not yet implemented, MCP parses stdout/stderr as raw text and estimates tokens.

### 14.2.7 Progressive Disclosure via Handles

**Current TE capability:**
- Large outputs stored with handle ID
- `te --handle res_01H...` retrieves stored result
- `te --handle res_01H... --chunk N` for pagination (planned)

**MCP integration:**
- If TE returns a handle, MCP includes it in response
- Agent can call `run_cmd(command="te --handle res_01H...")` to get more
- Budget tracking ensures agent doesn't retrieve entire codebase

**Example flow:**
```
Agent: run_cmd("rg 'TODO' .")
MCP → TE: subprocess with TE_AGENT_ID=claude-dc
TE: Finds 500 matches, returns first 50 + handle
MCP response: {
  "stdout": "... 50 matches ...",
  "meta": {
    "truncated": true,
    "total_matches": 500,
    "handle": "res_01H...",
    "hint": "Use 'te --handle res_01H...' for full results"
  }
}
Agent: (decides it needs more) run_cmd("te --handle res_01H... --chunk 1")
```

### 14.2.8 Docker Compose Topology

**Decision:** Single container for M5. MCP + TE + RAG daemon all colocated.

```yaml
# docker-compose.yml
version: '3.8'
services:
  llmc-mcp:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    environment:
      - LLMC_ROOT=/app
      - LLMC_CONFIG=/app/llmc.toml
      - LLMC_MCP_TOKEN=${LLMC_MCP_TOKEN}
    volumes:
      # Persist telemetry and RAG index
      - llmc-data:/app/.llmc
      # Optional: mount host code for development
      - ${HOST_REPO:-./}:/app:ro
    ports:
      - "8080:8080"  # HTTP transport (future)
    stdin_open: true  # For stdio transport
    tty: true

volumes:
  llmc-data:
```

**Volume mounts:**
- `/app/.llmc` → persists TE telemetry SQLite, RAG index, token audit CSV
- Optional host mount for development (read-only in prod)

### 14.2.9 Dockerfile Structure

```dockerfile
FROM python:3.11-slim

# Non-root user
RUN useradd -m -s /bin/bash llmc
WORKDIR /app

# System deps for RAG (ripgrep, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY --chown=llmc:llmc . .

# Create data directories
RUN mkdir -p /app/.llmc /app/artifacts && chown -R llmc:llmc /app

USER llmc

# Entry point
ENTRYPOINT ["python", "-m", "llmc_mcp.server"]
```

### 14.2.10 Config Additions for M5

```toml
[mcp.session]
# Default session context (can be overridden per-call)
default_agent_id = "claude-desktop-mcp"
default_model = "unknown"
# Session ID generated per conversation if not provided

[mcp.te]
enabled = true
script_path = "scripts/te"  # Relative to LLMC_ROOT
json_mode = true  # Request JSON output from TE
timeout = 30  # Override TE's internal timeout
passthrough_on_failure = true  # If TE fails, fall back to direct exec

[mcp.resources]
# Sidecar documents exposed as MCP resources
sidecars = [
    "DOCS/agents.core.min.md",
    "DOCS/contracts.env.min.md",
]

[mcp.docker]
# Settings only relevant when running in container
data_volume = "/app/.llmc"
persist_telemetry = true
persist_token_audit = true
```

### 14.2.11 Open Questions (All Resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | Transport inside Docker | **No transport** - direct subprocess calls |
| 2 | MCP ↔ TE relationship | **MCP calls TE** - TE doesn't know MCP exists |
| 3 | Agent identification | **Explicit metadata** via env vars, never inferred |
| 4 | Compose topology | **Single container** for M5, split later if needed |
| 5 | Tool surface | **Named semantic tools** (te_run, repo_read, etc.) |
| 6 | Budget handling | **MCP/orchestrator concern** - TE just logs |
| 7 | TE JSON output mode | **Add `--json` flag** - cleaner contract for MCP integration |
| 8 | Handle storage location | **TE default** - `.llmc/te_handles/` already works |
| 9 | Fallback when TE unavailable | **Config flag** - `passthrough_on_failure = true` default |
| 10 | `rg` through TE grep handler | **Passthrough for M5** - enrich in R2 roadmap item |

### 14.2.12 M5 Acceptance Criteria

- [ ] Dockerfile builds and runs MCP server
- [ ] `docker-compose up` starts functional MCP
- [ ] Named tools implemented: `te_run`, `repo_read`, `rag_query`
- [ ] `te_run` routes through TE via subprocess
- [ ] Session context (agent_id, session_id, model) passed to TE as env vars
- [ ] TE telemetry persists across container restarts
- [ ] MCP resources expose sidecar documents
- [ ] Observability metrics include TE latency
- [ ] Config flag to disable TE routing (fallback to direct exec)
- [ ] README documents container usage and tool surface

---

## 15. Risks & Mitigations
- **Full access + run_cmd:** Accepted risk; callers are trusted; emphasize allowlist + timeouts.
- **Config sprawl:** Single `McpConfig` source; startup logs show effective config.
- **RAG mismatch:** Bootloader tests assert AGENTS/CONTRACTS compatibility.
- **Observability overhead:** Toggle off; sampling possible post‑MVP.

---

## 16. Acceptance Criteria (MVP Ship)
- All endpoints function with token auth and limits; configs honored.
- RAG bootloader returns scoped snippets with provenance; no cache.
- Tools operate across `/`; run_cmd uses allowlist & timeouts.
- Observability toggles work; metrics/logs visible when enabled.
- Benchmarks: **≥ 40%** token reduction vs Desktop Commander baseline.
- Perf/SLOs met; tests pass in CI.

---

## 17. Appendix A — OpenAPI‑ish Sketch
```yaml
openapi: 3.0.0
info: { title: LLMC MCP, version: v0 }
paths:
  /health:
    get: { responses: { '200': { description: OK } } }
  /invoke_agent:
    post:
      requestBody: { required: true }
      responses: { '200': { description: OK }, '4xx': {}, '5xx': {} }
  /tool:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [session_id, name, args]
      responses: { '200': {}, '401': {}, '403': {}, '422': {}, '429': {} }
  /rag/search:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [q, scope]
  /rag/bootload:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [session_id, task_id]
components: {}
```

---

## 18. Appendix B — Pseudocode (FastAPI)
```python
app = FastAPI()

@app.middleware("http")
async def auth_and_limits(req, call_next):
    cid = get_or_make_correlation_id(req)
    if config.auth.enabled and not check_token(req):
        return err(401, "AUTH_FAILED", cid)
    if over_rate_or_concurrency(req):
        return err(429, "RATE_LIMITED", cid)
    try:
        resp = await call_next(req)
    except ValidationError as e:
        return err(422, "BAD_ARGS", cid, hint=str(e))
    except Exception as e:
        log_error(cid, e)
        return err(500, "INTERNAL", cid)
    return resp

@router.post("/tool")
def tool(req: ToolRequest):
    if req.name == "read_file":
        return read_file(req.args)
    if req.name == "list_dir":
        return list_dir(req.args)
    if req.name == "stat":
        return stat_path(req.args)
    if req.name == "run_cmd":
        return run_cmd(req.args)  # allowlist + timeout
    raise HTTPException(422, "unknown tool")

@router.post("/rag/search")
def rag_search(body: RagSearchRequest):
    return rag_adapter.search(
        body.q,
        scope=body.scope,
        k=min(body.k, cfg.rag.top_k),
        budget=min(body.budget_tokens, cfg.rag.token_budget)
    )
```

---

## 19. Roadmap Notes

### R1. write_file/edit_file Tools (Post-MVP Priority)
Add mutation capabilities with minimal prompt overhead. Research Anthropic's "Building Effective Agents" whitepaper for guidance on lean tool descriptions that avoid DC-style prompt bloat (~500+ lines for write semantics).

**Goal:** Efficient file mutations without sacrificing token efficiency.

**Research questions:**
- What's the minimum viable tool description for safe writes?
- Can we rely on agent intelligence vs. defensive prompting?
- How do other MCP implementations handle file mutations?

### R2. TE Enhancements for MCP
- `--json` output mode for structured responses
- Budget enforcement (hard caps, graceful degradation)
- Chunk-based handle retrieval (`--chunk N`)
- Additional enriched commands beyond grep/cat/find

### R3. Multi-Transport Support (M6+)
- HTTP transport for non-Claude-Desktop clients
- Optional reverse proxy (Caddy/Nginx) for TLS termination
- WebSocket for streaming responses

### R4. Advanced Features (Deferred)
- Hairpin relay transport
- Policy/ACL enforcement
- Envelopes/handles with staleness re-validation
- Dynamic tool filtering
- Anti-stomp session coordination
- Semantic caching at MCP layer

### R5. Gemini TUI Post-Completion Screen
Metrics/turns/quick actions display after task completion.

---

## 20. Appendix C — Current Implementation Status

**As of 2025-12-01:**

| Milestone | Status | Tests | Notes |
|-----------|--------|-------|-------|
| M0 | ✅ Complete | 7 smoke | Config, health, auth skeleton |
| M1 | ✅ Complete | 7 fs | read_file, list_dir, stat |
| M2 | ✅ Complete | 4 rag | rag_search, bootload |
| M3 | ✅ Complete | 5 exec | run_cmd with allowlist |
| M4 | ✅ Complete | 19 obs | Metrics, JSON logs, CSV audit |
| M5 | 🚧 Designed | - | Docker + TE integration |
| M6 | ⏳ Pending | - | Benchmarks |

**Total tests:** 42
**Lines of code:** ~1,500 (excluding tests)

**Files:**
```
llmc_mcp/
├── __init__.py          # v0.1.0
├── config.py            # 210 lines - McpConfig + McpObservabilityConfig
├── server.py            # ~475 lines - MCP server + handlers
├── observability.py     # 340 lines - metrics/logging/audit
├── test_smoke.py        # 7 tests
├── test_observability.py # 19 tests
└── tools/
    ├── __init__.py
    ├── fs.py            # 390 lines - filesystem + security
    ├── rag.py           # 150 lines - direct RAG adapter
    ├── exec.py          # 150 lines - run_cmd + allowlist
    ├── test_fs.py       # 7 tests
    ├── test_rag.py      # 4 tests
    └── test_exec.py     # 5 tests
```
