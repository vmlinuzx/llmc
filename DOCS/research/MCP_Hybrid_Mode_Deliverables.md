# MCP Hybrid Bootstrap Mode — Implementation Research Deliverables

Date: 2025-12-15  
Scope: Validate feasibility + security + real token overhead against the **current repo snapshot** (llmc-20251215-191132.zip).

This document corresponds to the deliverables you outlined in the research prompt and the SDD.

---

## Quick reality check vs the SDD text

Your SDD assumes:
- “23 tools” in classic mode
- “~41KB / ~10,250 tokens” tool overhead
- `run_cmd` is allowlist-enforced and **not** isolation-gated

In the current repo snapshot:
- **Classic mode registers 27 MCP tools** (not 23).  
- The **serialized tool schemas** (name + description + inputSchema) total **~10,458 chars (~2,615 tokens via chars/4)**, not ~41KB/~10k tokens.  
- `run_cmd` is currently **hard isolation-gated** in `llmc_mcp/tools/cmd.py` via `require_isolation("run_cmd")`, and the TOML’s `run_cmd_allowlist` is **not wired into config** (config currently loads `run_cmd_blacklist`).

None of these kill the hybrid idea — but they *do* change the economics and the implementation plan.

---

## D1 — Token overhead spreadsheet

### What I measured
I parsed the `TOOLS: list[Tool] = [...]` block from `llmc_mcp/server.py`, AST-literal-evaluated each tool’s:
- `name`
- `description`
- `inputSchema`

Then serialized each tool as JSON: `{"name":..., "description":..., "inputSchema":...}` and measured character length.

Token estimate used here: **chars/4** (cheap heuristic; good enough for relative comparisons).

### Outputs
- Spreadsheet: `MCP_Token_Overhead_Tool_Sizes.xlsx`
  - Sheet `ToolSizes`: per-tool chars + token estimate + category
  - Sheet `Scenarios`: Classic vs Code-Exec vs Hybrid totals

### Scenario totals (current repo)
| Scenario | Tools | Chars | Tokens est (chars/4) | Reduction vs Classic |
|---|---:|---:|---:|---:|
| Classic (all MCP tools) | 27 | 10,458 | ~2,615 | baseline |
| Code execution mode (bootstrap + execute_code + 00_INIT) | 4 | 1,884 | ~471 | ~82% |
| Hybrid (nav + write + run_cmd + 00_INIT) | 6 | 2,505 | ~626 | ~76% |
| Hybrid (nav + write + run_cmd + execute_code + 00_INIT) | 7 | 3,254 | ~814 | ~69% |

**Meets your “50%+ token reduction” requirement** either way.

---

## D2 — Security control audit trace

### linux_fs_write / linux_fs_edit (✅ good, already bounded)

**Trace (write):**
`LlmcMcpServer._handle_fs_write`  
→ `llmc_mcp.tools.fs_protected.write_file_protected()`  
→ `llmc_mcp.tools.fs.validate_path()`  
→ `llmc_mcp.tools.fs.check_path_allowed()` (Path.relative_to against allowed_roots)  
→ unprotected write (`llmc_mcp.tools.fs.write_file`)

**Controls present:**
- **allowed_roots enforcement**: validate_path rejects any resolved path not under an allowed root.
- **path normalization**: `Path(...).resolve()` collapses `..` traversal.
- **symlink escape detection**: `_check_symlink_escape` rejects symlinks that resolve outside allowed_roots.
- **device file rejection**: rejects block/char special files.
- **MAASL anti-stomp**: write/edit/move/delete acquire CRIT_CODE locks by resolved path.

**Result:** The write tools already match the “structurally bounded” claim.

### run_cmd (⚠️ NOT currently usable without isolation, and allowlist is miswired)

**Trace (today):**
`LlmcMcpServer._handle_run_cmd`  
→ `llmc_mcp.tools.cmd.run_cmd()`  
→ `require_isolation("run_cmd")` (hard fail on bare metal)

**Two big issues for hybrid:**
1. **Isolation gate:** hybrid requires `run_cmd` to work without setting `LLMC_ISOLATED=1`. Today it cannot.
2. **Config mismatch:** `llmc.toml` defines `run_cmd_allowlist`, but `llmc_mcp/config.py` loads `run_cmd_blacklist`, and `cmd.py` enforces a **blacklist**, not an allowlist.

**Security note (important):**  
If you allow `bash`, `sh`, `python`, `python3`, `pip`, etc. on *host*, `run_cmd` becomes **arbitrary code execution** (not “bounded”).  
So hybrid-safe `run_cmd` must use a **host-safe allowlist** (e.g., `ls`, `cat`, `rg`, `grep`, `find`, `head`, `tail`, `wc`, `sort`, `uniq`) and ideally **exclude** shells and interpreters by default.

### execute_code (✅ already isolation-gated)
`llmc_mcp.tools.code_exec.execute_code()` calls `require_isolation("execute_code")`. Keep as-is.

---

## D3 — Implementation diff (annotated changes)

This is written as an “annotated diff plan” (not a patch yet), aligned to your constraints.

### 1) Add mode + hybrid config
**Files:**
- `llmc_mcp/config.py`
- `llmc.toml`

**Add:**
- `[mcp] mode = "classic" | "hybrid" | "code_execution"` (default classic for existing installs)
- `[mcp.hybrid] promoted_tools = [...]`
- (optional) `[mcp.hybrid] include_execute_code = false/true`
- (optional) `[mcp.hybrid] bootstrap_budget_warning_chars = 15000`

**Also fix:**
- Wire TOML `run_cmd_allowlist` into config (keep blacklist too for backward compat).

### 2) Server mode selection + _init_hybrid_mode()
**File:**
- `llmc_mcp/server.py`

**Add:**
- `_init_hybrid_mode()` that selects a small tool set:
  - always: `read_file`, `list_dir`, `00_INIT`
  - plus config-promoted: `linux_fs_write`, `linux_fs_edit`, `run_cmd` (minimum viable)
  - optional: include `execute_code` (it will error unless isolated; that’s OK)

### 3) Make run_cmd host-safe in hybrid (and keep isolation for code-exec if you want)
**Files:**
- `llmc_mcp/tools/cmd.py`
- `llmc_mcp/config.py`
- `llmc_mcp/server.py`

**Recommended approach:**
- Replace blacklist-only enforcement with:
  - `allowlist` (required for host mode)
  - optional `blacklist` (extra deny list)
- Add a flag / parameter so the server decides whether `run_cmd` requires isolation:
  - `run_cmd(..., require_isolation=True|False, allowlist=[...])`

**Hybrid rule:**
- `require_isolation=False`
- allowlist = **host-safe** list (no shells/interpreters)

**Code-exec rule:**
- Keep `require_isolation=True` (status quo), or keep it disabled depending on your threat model.

### 4) Prompt update
**File:**
- `llmc_mcp/prompts.py`

Add a short “Hybrid mode” section:
- Direct host tools: fs_write/fs_edit + run_cmd (host-safe)
- Sandbox tools: execute_code (requires isolation; files ephemeral)

---

## D4 — Test plan for hybrid mode

### Unit tests
- Tool selection:
  - Hybrid registers exactly `read_file`, `list_dir`, `00_INIT` + configured promoted tools.
- Write works without isolation:
  - fs_write creates file within allowed_roots
  - fs_edit replaces expected text
- Path traversal:
  - `../../etc/passwd` rejected
  - symlink escape rejected
- MAASL:
  - concurrent write attempts produce ResourceBusyError results (or equivalent)
- run_cmd safety:
  - a disallowed binary is rejected (allowlist)
  - `bash -c ...` rejected by allowlist
  - `python -c ...` rejected by allowlist
  - `ls; rm -rf /` does not execute `rm` (shell=False + split) and should fail cleanly

### Integration tests
- Start server in hybrid mode and verify `tools/list` includes the right tool names.
- Call `linux_fs_write` and confirm file exists on disk.
- Call `run_cmd` for `ls` (works), and for `bash` (blocked).
- Call `execute_code` without isolation (must return isolation error).

---

## D5 — ADR draft (short)

**Decision:** Add `mcp.mode = hybrid` to support a small, direct MCP toolset including bounded host write operations, while keeping sandboxed code execution isolation-gated.

**Why:**
- Hybrid preserves core “edit the repo” workflows without stuffing the handshake with every tool.
- Write tools are already protected by allowed_roots + symlink/device checks + MAASL locks.
- `run_cmd` can be made safe **only** with a host-safe allowlist (no shells/interpreters).

**Consequences:**
- Need a clear separation between **host-safe** command exec and **sandbox** code exec.
- Config schema becomes slightly more complex (mode + hybrid section).
- Some users may be confused if `execute_code` is visible but fails on non-isolated hosts → prompt must be explicit.

---

## Files produced

- `MCP_Token_Overhead_Tool_Sizes.xlsx`
- (this file) `MCP_Hybrid_Mode_Deliverables.md`
