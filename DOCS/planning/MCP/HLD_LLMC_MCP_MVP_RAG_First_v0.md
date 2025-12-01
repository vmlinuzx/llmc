
# High‑Level Design — LLMC MCP (MVP, RAG‑First)
**Version:** v0 • **Date:** 2025-12-01 18:16:37 • **Owner:** LLMC  
**Scope:** Minimal MCP that works with LLMC’s RAG system, direct exposure by default, no TE wrappers or caching, config‑driven.

---

## 1. Problem & Goals
LLMC needs an MCP server that **does not pre‑prompt bloat**, pushes **context injection to server‑side via RAG**, and exposes a **small, predictable tool surface**. The MVP must be:
- **Direct‑exposed** on the home network with a local domain (hairpin later).
- **Config‑first** (all behavior in `llmc.toml`, with CLI/ENV overrides).
- **Fresh‑only** (no semantic cache in MCP; LLMC handles freshness).
- **Cheap & small**: tiny PRs, feature‑flagged, reversible.

**Non‑Goals (MVP):**
- Hairpin relay, envelopes/handles, staleness re‑validation, policy/ACL enforcement, TE wrappers, anti‑stomp, dynamic tool filtering, differential prompting.

---

## 2. Locked Decisions (MVP)
- **Topology:** Direct exposure with optional reverse proxy (Caddy/Nginx).  
- **Auth:** Static bearer token header: `X-LLMC-Token: <secret>` (no rotation).  
- **Tools:** Full filesystem (`/`) and `run_cmd` **enabled** (danger accepted).  
- **RAG:** Thin “bootloader” adapter; follows **AGENTS.md/CONTRACTS.md** conventions; no cache here.  
- **Data egress:** Allowed. MCP may return raw payloads.  
- **Observability:** Flag‑gated (metrics/logs/audit via `llmc.toml`).  
- **Config:** All keys live under **MCP CONFIGURATION** in `llmc.toml` (see config spec).

References: `mcp_mvp_inputs_locked.md`, `mcp_config_spec.md` (both already generated in this project context).

---

## 3. Architecture Overview
**Components**
1. **HTTP Front Door** (optional reverse proxy) — TLS/limits/rate‑limit (if used).  
2. **MCP Core (FastAPI)** — endpoint router, auth middleware, request limits.  
3. **Auth Module (token)** — validates `X-LLMC-Token` if `mcp.auth.mode="token"`.  
4. **Tool Adapter** — executes tool calls (`read_file`, `list_dir`, `stat`, `run_cmd`).  
5. **RAG Adapter (Bootloader)** — `rag.search` & `rag.bootload` calling LLMC.  
6. **Observability** — metrics, logs, correlation IDs (flag‑gated).  
7. **Config Loader** — merges Defaults ⟶ TOML ⟶ ENV ⟶ CLI; exposes `McpConfig`.  
8. **Rate/Concurrency Gates** — basic per‑token caps (configurable).

**Data Flow (MVP)**  
```
LLM Client ──(HTTP, token)──> MCP Core ──┬──> Tool Adapter ──> Host FS/Exec
                                         └──> RAG Adapter  ──> LLMC RAG
                              ↑
                         Observability (metrics/logs)
```

**Runtime Modes**
- **Direct exposure**: LLM tool calls the MCP over HTTP(S) using the token.  
- **Local dev**: curl/httpie, same token.

---

## 4. Endpoints (v0)
### 4.1 Health
- `GET /health` → `200 OK` `{ "ok": true, "version": "v0" }`

### 4.2 Invoke Agent (pass‑through + RAG bootloader)
- `POST /invoke_agent`  
  **Request:**  
  ```json
  {
    "session_id": "S",
    "role": "Beatrice|Otto|Rem|Grace",
    "user_msg": "text",
    "inject_context": ""   // optional pre‑injected context (rare in MVP)
  }
  ```
  **Behavior:** For MVP, this endpoint primarily demonstrates RAG bootloading and echoes a minimal contract back to the caller (actual model call is external to MCP).  
  **Response:**  
  ```json
  { "text": "[MCP v0] received; RAG bootload available; see /rag/search." }
  ```

### 4.3 Tool
- `POST /tool`  
  **Request:**  
  ```json
  { "session_id": "S", "name": "read_file|list_dir|stat|run_cmd", "args": {} }
  ```
  **Response:** Raw data **(egress allowed in MVP)**, JSON body with `data` and `meta` fields.  
  **Errors:** see §6.

### 4.4 RAG (bootloader)
- `POST /rag/search`  
  **Request:**  
  ```json
  { "q": "query", "scope": "repo|docs|both", "k": 3, "budget_tokens": 600 }
  ```
  **Response:**  
  ```json
  { "snippets": [{"text":"...", "src":"path#Lx-Ly", "score":0.82}], "provenance": true }
  ```
- `POST /rag/bootload`  
  **Request:** `{ "session_id":"S", "task_id":"T" }`  
  **Response:** minimal plan/scope derived from AGENTS.md/CONTRACTS.md (strings/keys only).

> Note: Handles/envelopes endpoints are **not** part of MVP v0. They’ll be introduced post‑MVP.

---

## 5. Tool Semantics (MVP)
- **read_file**: supports offset/length; returns raw text (UTF‑8).  
- **list_dir**: returns file/dir names.  
- **stat**: returns size, mtime, mode, type.  
- **run_cmd**: enabled; executes allow‑listed binaries; returns stdout/stderr/exit code.  
- **FS roots**: `allowed_roots = ["/"]` for your environment; validated and normalized.  
- **Outbound network**: allowed in MVP (your risk).

Example `POST /tool` (read_file):
```json
{ "session_id":"S", "name":"read_file", "args": {"path":"/etc/hosts","offset":0,"length":2048} }
```

---

## 6. Error & Status Model
Standard HTTP codes with a simple envelope:
```json
{ "code":"ERR_CODE", "message":"human message", "hint":"optional", "correlation_id":"uuid" }
```
- `401` unauthorized (missing/invalid token)  
- `403` forbidden (tool disabled or out of allowed roots)  
- `413` payload too large  
- `422` validation error (bad args)  
- `429` rate limit or concurrency cap hit  
- `500` unhandled error (never include secrets; log correlation_id)

---

## 7. Configuration (authoritative)
All behavior is configured via `llmc.toml` (MCP CONFIGURATION section). See **mcp_config_spec.md** for the full schema. Key MVP toggles:
- `mcp.enabled`, `mcp.server.host|port|tls_enabled`  
- `mcp.auth.mode="token"`, `mcp.auth.header`, `mcp.auth.token_env`  
- `mcp.tools.enable_run_cmd`, `mcp.tools.allowed_roots`, timeouts, allow_outbound_network  
- `mcp.rag.jit_context_enabled`, `mcp.rag.default_scope`, `mcp.rag.top_k`, `mcp.rag.token_budget`  
- `mcp.observability.enabled`, metrics/logging flags  
- `mcp.limits.rate_limit_rps`, `...burst`, `...concurrency_per_token`, `...max_request_bytes`

**Precedence:** CLI ⟶ ENV ⟶ TOML ⟶ defaults. MCP logs the effective config (minus secrets) on startup.

---

## 8. Security (MVP posture)
- **Direct exposure** with **static bearer token**. No rotation in MVP.  
- **No policy/ACL enforcement** beyond basic tool toggles & root checks.  
- **Path normalization** and traversal/escape checks.  
- **run_cmd** is on and dangerous by design for your environment; allow‑list binaries.  
- Optional reverse proxy can layer TLS/rate‑limit; not required for LAN MVP.

**Roadmap hardening:** mTLS/HMAC, hairpin relay, policy model (actions/locations/data types/egress), envelopes/handles with staleness checks, outbound allow‑lists.

---

## 9. Observability & SLOs
Flag‑gated by `mcp.observability.enabled`.
- **Metrics** (Prometheus): HTTP latency, errors, auth failures, rate‑limit drops, tokens in/out (if enabled).  
- **Logs:** JSON with correlation IDs; level from config.  
- **SLO targets (MVP):**  
  - No‑op p95 ≤ 15 ms  
  - Single tool call p95 ≤ 150 ms  
  - RAG search p95 ≤ 200 ms (delegated to LLMC)  
  - Error rate < 0.1% normal load

---

## 10. Performance & Limits
- Request read timeout 10 s; idle 60 s; exec timeout 30 s.  
- Body ≤ 256 KiB, header ≤ 16 KiB (configurable).  
- Rate limit 10 r/s, burst 20; concurrency cap per token 8 (configurable).

---

## 11. Deployment
- **Docker image** + optional **docker‑compose**; binds to `host:port` from config.  
- Optional **reverse proxy** sample (Caddyfile) under `/deploy/`.  
- Requires `LLMC_MCP_TOKEN` env when `mcp.auth.mode="token"`.

---

## 12. Testing & Validation
**Unit:** config merge/validation; token auth; path normalization; arg validation.  
**E2E:** health; auth fail/success; each tool happy/sad; RAG bootloader contract.  
**Perf:** latency budgets under synthetic load; rate‑limit and concurrency caps.  
**Security smoke:** path traversal, symlink escape, oversized payload, command injection attempts.  
**Benchmarks:** compare tokens vs Desktop Commander pre‑prompt baseline; goal ≥ **40%** reduction (primarily from no pre‑prompt + RAG‑first).

---

## 13. Risks & Mitigations
- **Security exposure** (full `/` + run_cmd): accepted risk by owner; document clearly; default OFF for general users.  
- **RAG scope drift**: MVP defers to LLMC’s AGENTS/CONTRACTS; mismatch mitigated by bootloader tests.  
- **Prompt creep**: none in MCP; tool docs not injected in MVP.  
- **Observability overhead**: toggle off via config if needed.

---

## 14. Rollout & Rollback
- Branch naming: `feat/mcp-M#-slug` • API version: `v0`.  
- Feature‑flags for risky toggles (`run_cmd`, outbound network, observability).  
- Rollback = disable via config/ENV; container restart; no data migration.

---

## 15. Roadmap (post‑MVP)
1) **Hairpin relay transport** (mutual TLS WS, no inbound port).  
2) **Policy/ACL model** (actions/locations/data types/egress).  
3) **Envelopes & handles** with staleness re‑validation.  
4) **TE wrappers** (rg/grep/cat) with latency guards.  
5) **Dynamic tool filtering & differential prompting**.  
6) **Anti‑stomp & session summaries**.  
7) **Gemini TUI post‑completion screen** (M7 addendum).

---

## 16. Acceptance Criteria (Ship/No‑Ship)
- MCP runs with static token auth; direct exposure reachable on LAN.  
- Tools (`read_file|list_dir|stat|run_cmd`) function across `/`.  
- RAG bootloader endpoints return scoped snippets with provenance, no cache.  
- Observability toggles work; metrics/logs show expected counters.  
- Benchmarks show **≥ 40%** token reduction vs Desktop Commander baseline.  
- All tests pass; latency within budgets.
