# Work Plan: RLM MCP Integration (1.Z)

## Context

### Original Request

Expose RLM (Recursive Language Model) analysis via MCP so MCP clients can invoke it programmatically (new MCP tool `rlm_query`).

### Key Decisions (confirmed)

- Transport scope for 1.Z: **stdio/local only** (no HTTP/SSE daemon hardening in this plan).
- Publish revised SDD as a new v2 doc (keep original for history).
- Default `mcp.rlm.profile = "unrestricted"`.
- `mcp.rlm.allow_model_override = false` by default.

### Mission-Critical Framing

Even with sandboxed code execution, `rlm_query` is effectively: **read local data + run analysis + potentially send content to an LLM provider**.

Hospital deployments require explicit egress controls, strict path policy, bounded resource usage, and auditable behavior.

### Primary References (patterns to follow)

- MCP handler response envelope (`{data, meta}` / `{error, meta}`): `llmc_mcp/server.py:1440` (read_file handler)
- Path canonicalization + allowed_roots enforcement + symlink escape checks: `llmc_mcp/tools/fs.py:64` (normalize_path / validate_path)
- RLM code-context load currently reads full file when given Path (DoS risk): `llmc/rlm/session.py:127`
- RLM trace is included by default unless disabled: `llmc/rlm/config.py:63`, `llmc/rlm/session.py:473`
- MCP config patterns (dataclasses + validate + TOML merge): `llmc_mcp/config.py:14`
- MCP security test patterns: `tests/mcp/test_fs.py`, `tests/mcp/test_smoke.py`
- SDD v2 draft to publish: `.sisyphus/drafts/SDD_RLM_MCP_Integration_1Z_v2.md`

---

## Work Objectives

### Core Objective

Add a safe, MCP-compliant `rlm_query` tool that runs RLM analysis over stdio transport with configurable egress/path limits and strong security/regression tests.

### Concrete Deliverables

- New SDD published as `DOCS/planning/SDD_RLM_MCP_Integration_1Z_v2.md`
- New MCP tool `rlm_query` registered and callable in classic mode
- New RLM MCP config surface (`[mcp.rlm]`) for profile/egress/path/time/budget limits
- Security hardening for file-based context loading (bounded reads + traversal protection)
- Tests: contract + security + handler-level integration

### Definition of Done

- Docs: `DOCS/planning/SDD_RLM_MCP_Integration_1Z_v2.md` exists and reflects the implemented contract
- Tests: `pytest -q` passes (or at minimum: targeted MCP + RLM test suite passes)
- Manual: `python -m llmc_mcp.server` + MCP client can call `rlm_query` successfully on a safe fixture

---

## Scope Boundaries

IN:

- stdio MCP tool implementation + config + tests + docs
- Hospital-grade guardrails that are enforceable in-process (path allowlist/denylist, model allowlist, time/budget caps)

OUT:

- HTTP/SSE daemon security design (OAuth/TLS/multi-user authz)
- Streaming responses
- Session persistence/resumption
- Repo-wide multi-file RLM context loading

---

## Verification Strategy

### Automated Tests (required)

- Pytest unit/contract tests for:
  - schema validation (oneOf, bounds)
  - response envelope correctness (no `error` key on success)
  - path traversal + symlink escape protections
  - default egress behavior (`allow_model_override=false`)
  - timeout enforcement (asyncio.wait_for)

### Manual Verification (required)

- Start stdio MCP server: `python -m llmc_mcp.server`
- Use an MCP client (Claude Desktop) to call `rlm_query` on a synthetic, non-sensitive file under allowed_roots
- Confirm returned JSON parses and includes `data.answer` + `meta` fields

---

## Task Flow

1) Publish SDD v2 → 2) Add MCP config surface → 3) Add tool + handler → 4) Harden RLM file load → 5) Tests → 6) Docs + manual verification

---

## TODOs

### 1) Publish the revised SDD v2 into DOCS

What to do:

- Create `DOCS/planning/SDD_RLM_MCP_Integration_1Z_v2.md` by copying content from `.sisyphus/drafts/SDD_RLM_MCP_Integration_1Z_v2.md`.
- Keep `DOCS/planning/SDD_RLM_MCP_Integration_1Z.md` unchanged for history.

References:

- `.sisyphus/drafts/SDD_RLM_MCP_Integration_1Z_v2.md` (source)

Acceptance criteria:

- File exists: `DOCS/planning/SDD_RLM_MCP_Integration_1Z_v2.md`
- Original remains: `DOCS/planning/SDD_RLM_MCP_Integration_1Z.md`

Parallelizable: YES (with task 2)

---

### 2) Add MCP config surface for RLM tool policy (`[mcp.rlm]`)

What to do:

- Add a new dataclass (e.g., `McpRlmConfig`) to `llmc_mcp/config.py`.
- Add it to the root `McpConfig` dataclass.
- Extend `load_config()` TOML merge logic to parse `[mcp.rlm]`.
- Add validation rules:
  - `profile` is one of `restricted|unrestricted`
  - default profile is `unrestricted`
  - `allow_model_override` defaults to false
  - in restricted profile:
    - disallow `allow_model_override=true`
    - require a non-empty `allowed_model_prefixes` allowlist (local-only)
    - strongly recommend (or enforce) that `mcp.tools.allowed_roots` is non-empty

References:

- Config patterns: `llmc_mcp/config.py:14` (dataclasses + validate)
- Existing limits config: `llmc_mcp/config.py:79` (`McpLimitsConfig`)

Acceptance criteria:

- `load_config()` succeeds with no `[mcp.rlm]` section (defaults apply)
- Invalid config combinations raise a clear ValueError
- Config supports:
  - `profile`
  - `enabled` feature flag for the tool
  - `allow_model_override`
  - `allowed_model_prefixes`
  - `denylist_globs`
  - `default_max_bytes`, `default_timeout_s`, `default_max_turns`

Parallelizable: YES (with task 1)

---

### 3) Register the new MCP tool definition (`rlm_query`)

What to do:

- Add `Tool(name="rlm_query", ...)` to `TOOLS` in `llmc_mcp/server.py`.
- Ensure JSON schema matches the SDD v2 contract:
  - `task` required, maxLength 5000
  - `oneOf`: exactly one of `path` or `context`
  - bounds for `budget_usd`, `max_bytes`, `timeout_s`, `max_turns`

References:

- Tool registry location: `llmc_mcp/server.py:55`
- Existing tool schema style: `llmc_mcp/server.py:55` (rag_search, read_file)

Acceptance criteria:

- `tests/mcp/test_smoke.py:test_tools_list` updated/extended so it expects `rlm_query` to exist in classic mode
- `TOOLS` includes `rlm_query` with correct schema

Parallelizable: NO (depends on task 2 if schema includes config-driven defaults, otherwise YES)

---

### 4) Implement `llmc_mcp/tools/rlm.py` (core tool logic)

What to do:

- Implement an async function (e.g., `mcp_rlm_query(...)`) that:
  - validates mutual exclusion (`path` xor `context`)
  - enforces task length and numeric bounds
  - resolves/reads files safely when `path` is provided:
    - use `llmc_mcp/tools/fs.py:validate_path` for canonicalization + allowed_roots
    - apply denylist_globs
    - read bounded bytes and reject oversized files with `error_code=file_too_large`
  - constructs an `RLMSession` with:
    - per-call budget cap
    - `trace_enabled = false` for MCP responses
    - `max_turns` override (default <= 5)
  - enforces egress policy:
    - if `allow_model_override` is false, reject provided `model`
    - if profile is restricted, ensure configured model(s) match `allowed_model_prefixes`
  - wraps execution in `asyncio.wait_for(..., timeout=timeout_s)`
  - returns a dict shaped as either `{data, meta}` or `{error, meta}` (never `error` key on success)

References:

- Path security helpers: `llmc_mcp/tools/fs.py:143` (validate_path)
- MCP response envelope: `llmc_mcp/server.py:1440` (read_file handler)
- RLM session entrypoint: `llmc/rlm/session.py:245` (run)
- RLM config/trace behavior: `llmc/rlm/config.py:63`, `llmc/rlm/session.py:473`

Acceptance criteria:

- Success response is parseable JSON with keys: `data.answer`, `meta.source`, `meta.model_used`, `meta.trace_included=false`
- Failure responses include: `error`, `meta.error_code`, `meta.retryable`
- `trace` is never returned in MCP output

Parallelizable: NO (depends on task 2)

---

### 5) Implement server handler + registration (`_handle_rlm_query`)

What to do:

- Add `_handle_rlm_query(self, args: dict) -> list[TextContent]` to `llmc_mcp/server.py`.
- Wire handler into classic mode `tool_handlers` map.
- Ensure hybrid mode can include it via `mcp.hybrid.promoted_tools`.
- If `mcp.rlm.enabled=false`, return a structured `{error, meta}` response indicating tool disabled.

References:

- Handler pattern: `llmc_mcp/server.py:1440` (_handle_read_file)
- Tool handler registration: `llmc_mcp/server.py:661` (_init_classic_mode)
- Hybrid handler registration: `llmc_mcp/server.py:746` (_init_hybrid_mode)

Acceptance criteria:

- Calling `_handle_rlm_query` directly returns correct JSON envelope
- `LlmcMcpServer` in classic mode lists `rlm_query`

Parallelizable: NO (depends on tasks 2-4)

---

### 6) Harden RLM file loading against DoS (shared layer)

What to do:

- Add a file-size guard to `RLMSession.load_code_context()` when given a Path so CLI usage can’t OOM on huge files.
- Ensure behavior is consistent with `load_context()` which already enforces `max_context_chars`.

References:

- Risky read: `llmc/rlm/session.py:127` (reads full file)
- Existing context guard: `llmc/rlm/session.py:99` (max_context_chars)

Acceptance criteria:

- Oversized file passed to `load_code_context(Path)` raises a clear ValueError (and does not allocate huge memory)

Parallelizable: YES (can be done alongside tasks 4-5)

---

### 7) Tests: contract, security, and handler-level integration

What to do:

- Add unit/contract tests for `rlm_query` tool logic:
  - invalid args, oneOf enforcement, bounds
  - success envelope contains no `error`
  - failure envelope includes `error_code`
- Add security tests:
  - path traversal blocked
  - denylisted patterns blocked
  - oversized files rejected (no truncation by default)
  - `model` override rejected by default
  - restricted profile rejects non-local model prefixes
- Add handler-level integration test similar to `tests/mcp/test_smoke.py` calling `server._handle_rlm_query(...)`.

References:

- FS security tests patterns: `tests/mcp/test_fs.py`
- Handler-level test patterns: `tests/mcp/test_smoke.py:60`

Acceptance criteria:

- `pytest tests/mcp -q` passes
- New tests cover the security-relevant branches (path policy, egress policy, timeout)

Parallelizable: YES (tests can be developed while implementation proceeds)

---

### 8) Docs + tool reference updates

What to do:

- Update MCP tool reference docs to include `rlm_query` (via existing docgen workflow).
- Add an ops note for hospital deployments (restricted profile config example + egress warning).

References:

- MCP docs generation script (exists per repo): `scripts/generate_mcp_docs.py`
- MCP tool reference location: `DOCS/reference/mcp-tools/index.md`

Acceptance criteria:

- `DOCS/reference/mcp-tools/` includes `rlm_query` description and schema
- Clear guidance exists for restricted profile in hospital contexts

Parallelizable: YES

---

### 9) Manual verification (stdio)

What to do:

- Run stdio server locally and invoke `rlm_query` from a real MCP client.
- Use a synthetic fixture file (no secrets/PHI).

Acceptance criteria:

- MCP client call returns `data.answer` and `meta` as specified
- Trace is not returned

Parallelizable: NO (depends on implementation)

---

## Commit Strategy

Aim for small, reviewable commits:

1. docs(planning): add SDD v2
2. feat(mcp): add McpRlmConfig and parsing
3. feat(mcp): add rlm_query tool + handler
4. fix(rlm): guard load_code_context file size
5. test(mcp): add rlm_query contract/security tests
6. docs(mcp): update tool reference
