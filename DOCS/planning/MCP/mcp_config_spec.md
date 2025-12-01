
# LLMC MCP — Configuration Spec (MVP)  
*Updated: 2025-12-01T18:08:39*

**Goal:** Nothing hard-coded. All MCP behavior toggled via `llmc.toml` (with CLI/ENV overrides). Observability is **flag-gated**.

---

## 1) Config File Location & Precedence
- Default file: `./llmc.toml`
- Alternate: `LLMC_CONFIG=/path/to/llmc.toml`
- **Precedence:** CLI flags ⟶ ENV ⟶ TOML ⟶ internal defaults
- On startup, MCP logs the **effective config** (minus secrets).

---

## 2) TOML Layout (MVP, RAG-first, direct exposure)
```toml
# ============================
# MCP CONFIGURATION (MVP)
# ============================
[mcp]
enabled = true
config_version = "v0"

[mcp.server]
host = "127.0.0.1"
port = 8080
base_url = "http://127.0.0.1:8080"
# TLS is optional in MVP; reverse proxy handles it if present
tls_enabled = false

[mcp.auth]
mode = "token"            # "token" | "mtls" (future)
header = "X-LLMC-Token"
token_env = "LLMC_MCP_TOKEN"
allow_unauthenticated = false

[mcp.tools]
enable_run_cmd = true
allowed_roots = ["/"]     # Your risk, your box
allow_outbound_network = true
# Fixed-arg allowlist for run_cmd (match by binary name)
run_cmd_allowlist = ["bash","sh","rg","grep","cat","ls","python","pip"]
# Timeouts (seconds)
exec_timeout = 30
read_timeout = 10
idle_timeout = 60

[mcp.rag]
jit_context_enabled = true
default_scope = "repo"    # "repo"|"docs"|"both"
top_k = 3
token_budget = 600

[mcp.observability]
enabled = true
metrics_prometheus_enabled = true
metrics_path = "/metrics"
csv_token_audit_enabled = false
csv_path = "./artifacts/token_audit.csv"
log_format = "json"       # "json" | "plain"
log_level = "info"        # "debug" | "info" | "warn" | "error"
retention_days = 0        # 0 = unlimited
include_correlation_id = true

[mcp.limits]
rate_limit_rps = 10
rate_limit_burst = 20
concurrency_per_token = 8
max_request_bytes = 262144   # 256 KiB
max_header_bytes  = 16384    # 16 KiB

# --- Roadmap (stubs only; no enforcement in MVP) ---
[mcp.security]  # future policy/ACL
policy_enabled = false
policy_file = "./policy.toml"

[mcp.transport.hairpin]  # future relay
enabled = false
relay_url = ""
mtls_enabled = false

[mcp.envelopes]  # not used in MVP
enabled = false

[mcp.handles]    # not used in MVP
enabled = false
ttl_seconds = 7200
```

---

## 3) ENV Variables (selected)
```
LLMC_CONFIG=/path/to/llmc.toml
LLMC_MCP_TOKEN=supersecrettoken
LLMC_MCP_PORT=8080
LLMC_MCP_HOST=127.0.0.1
LLMC_MCP_LOG_LEVEL=info
```

---

## 4) CLI Flags (map to TOML keys)
```
llmc mcp serve   --config ./llmc.toml   --mcp.enabled=true   --mcp.server.host=127.0.0.1   --mcp.server.port=8080   --mcp.auth.mode=token   --mcp.observability.enabled=true   --mcp.observability.metrics_prometheus_enabled=true
```
> Flags override ENV/TOML; dotted keys mirror the TOML structure.

---

## 5) Observability (flag-gated)
- `mcp.observability.enabled=false` ⇒ no metrics endpoint; only minimal logs.
- `metrics_prometheus_enabled=true` exposes `GET {mcp.observability.metrics_path}`.
- `csv_token_audit_enabled=true` appends per-turn token in/out deltas to `csv_path`.
- `include_correlation_id=true` injects/propagates `x-request-id` in logs/headers.

**Metrics (MVP):**
- `mcp_http_latency_ms{{route}}` (p50/p95/p99)
- `mcp_http_errors_total{{code}}`
- `mcp_tokens_in_total`, `mcp_tokens_out_total`
- `mcp_auth_failures_total`
- `mcp_rate_limit_drops_total`

---

## 6) Validation Rules
- If `mcp.auth.mode="token"`, `LLMC_MCP_TOKEN` must be present at start.
- If `enable_run_cmd=true`, warn on empty `run_cmd_allowlist`.
- If `allowed_roots` is empty, default to `["/"]` (MVP permissive behavior).
- Invalid combinations (e.g., `hairpin.enabled=true` with `tls_enabled=true`) log a **warning** (MVP), become **errors** post-MVP.

---

## 7) HLD Assumptions (what code will implement)
- Config loader merges **defaults ⟶ TOML ⟶ ENV ⟶ CLI** and logs the effective diff.
- Single source of truth struct (e.g., `McpConfig`) passed to all subsystems.
- Observability and auth wrap endpoints **only if flags are enabled**.
- Future features (hairpin, policy, envelopes/handles) read their flags now; no-ops in MVP.

---

## 8) Test Plan (config-level)
- Parse/merge precedence tests (TOML vs ENV vs CLI).
- Observability off: `/metrics` returns 404; on: returns 200 with counters.
- Auth off vs on: token required paths fail/succeed accordingly.
- Limits: oversize body triggers 413; rate-limit produces 429.
