# SDD: RLM Phase 1.2 - MCP Tool Integration (1.Z) (Revised v2)

Status: DRAFT (proposed new v2 doc; keep `DOCS/planning/SDD_RLM_MCP_Integration_1Z.md` for history)

Priority: P1

Added: 2026-01-25

Effort (re-estimated):
- Core wiring (tool + handler + basic tests): 0.5-1.0 day
- Hospital-grade hardening (path policy + egress controls + security tests + ops docs): 1.0-2.0 days

Depends On:
- 1.Y (bug fixes)
- Recommended: 1.X (RLM configuration surface) if RLM config is still changing

---

## 0. Context

### Original Request

Expose RLM (Recursive Language Model) analysis via MCP so MCP clients (Claude Desktop, Antigravity, agents) can invoke it programmatically.

### Why This Revision

The original SDD describes the happy path but is under-specified for safety-critical use. This revision:

- Makes the trust boundary explicit (local stdio vs daemon).
- Aligns the tool contract with existing LLMC MCP response conventions (`{data, meta}` / `{error, meta}`).
- Specifies confidentiality, egress, and path controls needed for hospital environments.
- Adds concrete failure modes, error codes, and a verification plan that tests security properties.

### Deployment Reality (from user)

- Hospital environment: expected to use local inference.
- Non-hospital/personal use: user intends to use large cloud LLMs heavily.

This implies the MCP tool must support multiple "profiles" (restricted vs unrestricted), controlled by config.

### Confirmed Decisions

- `mcp.rlm.allow_model_override = false` by default.

---

## 1. Problem Statement

RLM analysis is only accessible via CLI today:

```bash
llmc rlm query "What does this file do?" --file mycode.py
```

MCP clients cannot invoke RLM programmatically. This prevents agentic workflows from using RLM as a callable capability.

---

## 2. Goals and Non-Goals

### Goals

1. Expose a new MCP tool `rlm_query` that runs an `RLMSession` against either:
   - user-supplied `context` text, or
   - a server-resolved file path under allowed roots.
2. Provide a stable, parseable JSON response contract that matches existing LLMC MCP conventions.
3. Support two operational profiles via config:
   - Restricted (hospital-grade): local inference + strict file/path policy.
   - Unrestricted (developer/personal): allow cloud models and/or model override when explicitly enabled.

### Non-Goals (out of scope for 1.Z)

- Streaming/partial results over MCP.
- Session persistence/resumption.
- Multi-file context loading (repo-scale RLM).
- Any attempt to make "remote daemon" hospital-safe without dedicated authn/z design.

---

## 3. Trust Boundary and Deployment Modes

### 3.1 Supported Mode in 1.Z

**Stdio transport only (local, single-user)**:

- The MCP server is spawned locally by the MCP client (e.g., Claude Desktop).
- Security relies primarily on OS/process boundaries + `allowed_roots` restrictions.

### 3.2 Explicitly Deferred

**HTTP/SSE daemon / network exposure** is deferred to a separate SDD.

Rationale: the threat model changes significantly (multi-user authz, TLS, token rotation, abuse prevention, audit retention).

### 3.3 Confidentiality Reality

Even if RLM code execution is "sandboxed", the dominant risk for `rlm_query` is:

**Data egress**: file contents / context may be transmitted to an LLM provider if a cloud model is used.

Hospital-grade use requires an explicit egress policy.

---

## 4. MCP Interface Contract

### 4.1 Tool Name

`rlm_query`

### 4.2 Input Contract

#### Fields

- `task` (string, required): analysis question/instructions.
- `path` (string, optional): file path to analyze. (Renamed from `file_path` for consistency with existing MCP tools like `read_file`.)
- `context` (string, optional): raw text to analyze.
- `budget_usd` (number, optional): per-call budget cap.
- `model` (string, optional): model override.
- `max_bytes` (integer, optional): maximum bytes to read from `path`.
- `timeout_s` (integer, optional): hard timeout for the entire query.
- `max_turns` (integer, optional): cap on RLM reasoning turns (prevents runaway sessions).
- `language` (string, optional): language hint for parsing/navigation (e.g., "python").

#### Mutual Exclusion

Exactly one of `path` or `context` must be provided.

This must be enforced in BOTH:

1. JSON Schema (`oneOf`)
2. Runtime validation

#### Path Semantics (if `path` is used)

- Paths are validated and resolved using the same security policy as MCP filesystem tools.
  - Canonicalize (`resolve()`), prevent traversal, detect symlink escape.
  - Enforce `allowed_roots`.
  - Reject device files.
- Default policy: repo-relative paths are allowed; absolute paths are rejected unless explicitly enabled.
- File reads are bounded by `max_bytes` (default is conservative).

#### Egress / Model Semantics

The tool must implement an explicit egress policy controlled by config:

- Restricted profile (recommended for hospital deployments):
  - `model` override rejected.
  - Only local models permitted (operator-defined allowlist).
- Unrestricted profile:
  - `model` override allowed only if explicitly enabled.

Confirmed default:

- `allow_model_override = false`

If the egress policy rejects the requested model, the tool must return a structured error with a clear remediation message.

#### Input JSON Schema (proposed)

```json
{
  "type": "object",
  "properties": {
    "task": {"type": "string", "maxLength": 5000, "description": "Analysis task/question (max 5000 chars)"},
    "path": {"type": "string", "description": "File path to analyze"},
    "context": {"type": "string", "description": "Raw text context to analyze"},
    "budget_usd": {"type": "number", "minimum": 0.01, "default": 1.0},
    "model": {"type": "string", "description": "Optional model override (subject to policy)"},
    "max_bytes": {"type": "integer", "minimum": 1, "default": 262144},
    "timeout_s": {"type": "integer", "minimum": 1, "default": 300},
    "max_turns": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
    "language": {"type": "string"}
  },
  "required": ["task"],
  "oneOf": [
    {"required": ["path"], "not": {"required": ["context"]}},
    {"required": ["context"], "not": {"required": ["path"]}}
  ]
}
```

Notes:

- Default `max_bytes` is intentionally conservative (256KB). Operators can raise it.
- Default `timeout_s` aligns with `RLMConfig.session_timeout_seconds` (5 minutes) unless overridden.

### 4.3 Output Contract

LLMC MCP tools should return JSON that is stable for clients.

#### Success Response

Return:

```json
{
  "data": {
    "answer": "...",
    "session_id": "...",
    "budget_summary": {"total_cost_usd": 0.01}
  },
  "meta": {
    "source": {"type": "path", "path": "...", "bytes_read": 12345, "truncated": false},
    "model_used": "...",
    "trace_included": false
  }
}
```

Important:

- The success payload MUST NOT include a top-level `error` key.
  - The MCP server currently treats the presence of the JSON key `"error"` as a failure signal.

#### Error Response

Return:

```json
{
  "error": "Human-readable message",
  "meta": {
    "error_code": "...",
    "retryable": false
  }
}
```

---

## 5. Proposed Implementation Changes (high-level)

### 5.1 Tool Registration

Add a new `Tool(...)` entry to the `TOOLS` list in `llmc_mcp/server.py`.

Mode behavior to document:

- Classic mode: `rlm_query` is available when registered.
- Hybrid mode: `rlm_query` is available only if included in `mcp.hybrid.promoted_tools`.
- Code execution mode: `rlm_query` will exist as a stub (generated from `TOOLS`) but is not directly exposed as an MCP tool unless added to bootstrap tools.

### 5.2 Handler Pattern

Implement as:

- `llmc_mcp/tools/rlm.py`: pure functions that perform validation, config load, and session execution.
- `llmc_mcp/server.py`: add `_handle_rlm_query(self, args: dict) -> list[TextContent]` that calls the function and returns JSON text.

### 5.3 Safe File Reads

File reads must reuse MCP filesystem security helpers:

- `llmc_mcp/tools/fs.py:validate_path()` for canonicalization + allowlist checks.
- `llmc_mcp/tools/fs.py:read_file()` for bounded reads and device-file rejection.

Rationale: ensures consistent path policy across all MCP tools.

### 5.4 RLM Session Configuration

The handler must:

- Load RLM config relative to the MCP server's `repo_root`.
- Apply a per-call budget cap (`budget_usd`) with strict validation.
- Default to `trace_enabled = false` for MCP responses.

---

## 6. Failure Modes and Error Codes

Define explicit `error_code` values (examples):

| error_code | Scenario | retryable | Notes |
|-----------|----------|-----------|-------|
| invalid_args | schema / mutual exclusion / bounds | false | client must fix request |
| path_denied | outside allowed_roots / symlink escape / device file | false | include remediation |
| file_not_found | missing file | false | |
| file_too_large | exceeds max_bytes | false | recommend increasing limit or use context |
| egress_denied | model override not allowed / remote not allowed | false | hospital profile |
| budget_exceeded | budget cap reached | false | return partial? (default: error) |
| timeout | query exceeded timeout_s | maybe | retry depends on root cause |
| provider_error | LLM provider returned error | maybe | include provider class/message |
| internal_error | unexpected exception | maybe | log with correlation id |

Define whether partial results are allowed. Default recommendation for safety-critical use: **no partial answers on timeouts/budget exceed** unless explicitly enabled.

---

## 7. Security and Privacy Requirements

### 7.1 Hospital-Grade Minimum Requirements

1. Egress policy defaults to restricted/local-only.
2. `model` override disabled by default.
3. Path access restricted to repo workspace roots only (no arbitrary absolute paths).
4. Denylist sensitive filenames/patterns (minimum): `.env`, `*.pem`, `id_rsa*`, `*credential*`, `*token*`.
5. No logging of raw context or file contents.
6. Trace disabled by default.

### 7.2 Auditability

For each call, ensure logs/metrics record:

- correlation_id (from MCP server)
- tool name
- duration
- bytes read
- model used
- cost summary (if available)
- error_code (if failure)

No PHI/PII/secrets should be logged.

### 7.3 Threat Model Notes (non-exhaustive)

- Prompt injection is expected; do not grant filesystem breadth beyond required roots.
- Path traversal and symlink escape must be prevented.
- Large file DoS must be prevented.
- Cloud egress must be explicitly controlled (hospital profile).

---

## 8. Verification Plan

### 8.1 Unit / Contract Tests

- Schema enforcement:
  - requires `task`
  - exactly one of `path` or `context`
  - bounds checks (`budget_usd`, `max_bytes`, `timeout_s`)
- Output contract:
  - success responses contain `data` + `meta` and do NOT contain `error`
  - error responses contain `error` + `meta.error_code`

### 8.2 Security Tests

- Path traversal attempts (`../..`)
- Symlink escape fixture
- Denylisted filenames/patterns
- Device file rejection (as feasible in test environment)
- Oversized file behavior (`file_too_large`)

### 8.3 Resilience Tests

- Provider timeout simulation
- Budget exceeded simulation
- Cancellation / timeout handling (`timeout_s`)

### 8.4 End-to-End MCP Testing

Use existing MCP test harness patterns in `tests/mcp/` to validate:

- stdio handshake + tool discovery
- `tools/call` invocation of `rlm_query`

Note: any live-provider tests must use synthetic, non-sensitive fixtures only.

---

## 9. Acceptance Criteria

1. `rlm_query` is registered in MCP tool listing (classic mode).
2. `rlm_query` can be invoked over stdio and returns valid JSON.
3. Success payloads do not include a top-level `error` key.
4. Path policy is enforced via `allowed_roots` + canonicalization.
5. Default file read limit (`max_bytes`) prevents oversized file DoS.
6. Trace is disabled by default for MCP responses.
7. Unit + security tests cover key threat vectors.

---

## 10. Operational Notes (runbooks)

### 10.0 Configuration Surface (proposed)

This SDD proposes adding an MCP config subsection dedicated to RLM tool policy.

Example shape in `llmc.toml`:

```toml
[mcp.rlm]
enabled = true

# Profile controls (operator choice)
profile = "unrestricted" # "restricted" | "unrestricted"

# File access
allow_path = true
allow_absolute_paths = false
denylist_globs = ["**/.env", "**/*.pem", "**/id_rsa*", "**/*credential*", "**/*token*"]

# Size/time limits
default_max_bytes = 262144
default_timeout_s = 300

# Egress/model controls
allow_model_override = false
allowed_model_prefixes = []

# Hospital deployment recommendation:
# profile = "restricted"
# allow_model_override = false
# allowed_model_prefixes = ["ollama_chat/"]
```

Notes:

- `allowed_roots` remains in `[mcp.tools]` and is still enforced.
- In restricted profile, operators should set local-only model prefixes (e.g., Ollama) and treat this as an egress deny-by-default.
- In unrestricted profile, `allow_model_override=true` can be enabled in non-hospital environments.

### 10.1 Profiles

Document two recommended profiles:

1. Restricted (hospital): local inference only + file/path policy strict
2. Unrestricted (personal): allow cloud models and optional model override

### 10.2 Incident Response (minimum)

- If sensitive data was potentially sent to a cloud model:
  - disable MCP server / disable `rlm_query`
  - rotate any provider keys
  - review audit logs for scope

---

## 11. Out of Scope

- Streaming responses
- Session persistence
- Multi-file/repo-wide RLM context
- HTTP daemon security design
