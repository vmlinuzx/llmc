# AAR: Gap Analysis - MCP & Routing

**Date:** 2025-12-12
**Analyst:** Rem (Gap Analysis Demon)
**Scope:** `llmc_mcp` and `llmc/routing`

## Executive Summary
Two significant gaps were identified in the target codebase. One relates to system resilience (routing logic crash) and the other to security (command blacklist bypass). SDDs were created and worker agents successfully implemented tests to prove these gaps.

## Identified Gaps

### 1. Router Resilience (Uncaught Exceptions)
- **Description:** The `classify_query` function relies on external heuristics modules (`code_heuristics`, `erp_heuristics`). It lacks a `try/except` block. If a heuristic module raises an exception (e.g., regex error, config error), the entire routing subsystem crashes.
- **Severity:** Medium (Availability/Robustness)
- **Status:** **CONFIRMED**
- **Evidence:** `tests/gap/test_router_resilience.py` fails with an uncaught `ValueError` when `score_all` is mocked to raise one.
- **Remediation:** Wrap heuristic calls in `try/except Exception` and fallback to default route.

### 2. MCP Command Security (Blacklist Bypass)
- **Description:** The `validate_command` function in `llmc_mcp/tools/cmd.py` implements a blacklist that checks only the binary name (first token). It fails to inspect arguments.
- **Severity:** High (Security - if `run_cmd` enabled)
- **Status:** **CONFIRMED**
- **Evidence:** `tests/gap/test_mcp_cmd_validation.py` passes, verifying that:
    1. Blacklist correctly blocks `node` (direct).
    2. Blacklist correctly blocks `/usr/bin/node` (path resolution).
    3. Blacklist **FAILS** to block `bash -c "node ..."` (bypass).
- **Remediation:** Blacklisting is fundamentally flawed for shell commands. Recommendation is to either:
    1. Whitelist entire command strings (strict).
    2. Disable `run_cmd` by default (already done).
    3. Enforce sandboxing (already done via "Sandbox provides real security" comment).
    4. Improve validation to inspect args (partial fix, still fragile).

## Artifacts
- **SDDs:**
    - `tests/gap/SDDs/SDD-Router-Resilience.md`
    - `tests/gap/SDDs/SDD-MCP-Cmd-Validation.md`
- **Tests:**
    - `tests/gap/test_router_resilience.py` (Failing - Proof of Gap)
    - `tests/gap/test_mcp_cmd_validation.py` (Passing - Proof of Gap)
