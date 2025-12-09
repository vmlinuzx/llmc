# Security Audit Report - LLMC Codebase

**Date:** December 8, 2025  
**Auditor:** Rem the Penetration Testing Demon  
**Scope:** `llmc/`, `llmc_mcp/`, `scripts/`  

## 1. Executive Summary

- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Server (`llmc_mcp`), CLI (`llmc`), Scripts
- **Critical Vulnerabilities Found:** 2
- **Exploitability:** High (Remote Code Execution via MCP)

The codebase has a generally strong security posture regarding file access (`allowed_roots`) and command execution (`run_cmd` whitelist + isolation). However, a **critical vulnerability chain** exists in the `te_run` tool, which bypasses these protections and allows arbitrary command execution via the `te` CLI wrapper.

## 2. Threat Model

- **Assets:** User filesystem, RAG database, LLM API keys.
- **Adversaries:** Malicious MCP clients, untrusted RAG content, compromised agents.
- **Trust Boundaries:**
    - MCP JSON-RPC Interface (Input: Untrusted)
    - `llmc` CLI arguments (Input: Untrusted)
    - `llmc.toml` (Input: Trusted/Admin)

## 3. Vulnerabilities Found

### VULN-001: Command Injection in Tool Envelope (TE) CLI
- **Severity:** **Critical**
- **CWE:** CWE-78 (OS Command Injection)
- **File:** `llmc/te/cli.py:402`
- **Description:** The `_handle_passthrough` function constructs a command string by joining arguments with spaces and executing it with `subprocess.run(..., shell=True)`. This allows arbitrary command injection if arguments contain shell metacharacters (`;`, `|`, `&&`, `$()`).
- **Proof of Concept:**
  ```python
  # Injected via CLI args
  args = ["echo", "hello; rm -rf /"]
  # Becomes: "echo hello; rm -rf /"
  # Executed by shell
  ```
- **Remediation:**
  Use `shell=False` and pass the list of arguments directly to `subprocess.run`.
  ```python
  subprocess.run(cmd_parts, shell=False, ...)
  ```

### VULN-002: MCP Isolation Bypass via `te_run`
- **Severity:** **Critical**
- **CWE:** CWE-284 (Improper Access Control)
- **File:** `llmc_mcp/tools/te.py`
- **Description:** The `te_run` tool exposed by the MCP server does not call `require_isolation("te_run")`. This bypasses the containerization requirement enforced on other dangerous tools like `run_cmd` and `execute_code`. Combined with VULN-001, this allows an MCP client to execute arbitrary commands on the host system without restriction.
- **Impact:** Full Remote Code Execution (RCE) on the host.
- **Remediation:**
  Add `require_isolation` check to `te_run` or remove the tool if not strictly necessary.

### VULN-003: RUTA Judge Dependency Missing (Potential Denial of Service)
- **Severity:** Low (Operational)
- **File:** `llmc/ruta/judge.py`
- **Description:** The code imports `simpleeval` to safely evaluate expressions, but the package is missing from the environment. This causes the RUTA Judge to crash. While this prevents the previous `eval()` injection vulnerability, it breaks functionality.
- **Remediation:** Add `simpleeval` to project dependencies.

## 4. Security Strengths

- **MCP Architecture:** The MCP server uses `stdio` transport, reducing network attack surface.
- **File System Sandbox:** `llmc_mcp/tools/fs.py` implements robust path traversal protection using `pathlib.resolve()` and `allowed_roots` enforcement.
- **Command Whitelisting:** The `run_cmd` tool correctly uses `shlex.split` and enforces a blacklist (though whitelist is preferred).
- **Isolation Enforcement:** Critical tools (`run_cmd`, `execute_code`) are gated by `require_isolation`, ensuring they only run in containerized environments (except for the `te_run` oversight).

## 5. Recommendations

### P0 (Immediate Fix)
1.  **Patch `llmc/te/cli.py`:** Remove `shell=True` usage.
2.  **Secure `llmc_mcp/tools/te.py`:** Add `require_isolation("te_run")`.

### P1 (Fix Soon)
1.  **Install `simpleeval`:** Fix the missing dependency to restore RUTA functionality securely.
2.  **Audit Scripts:** Review `scripts/` for loose `subprocess` calls (found several using `shell=True` in tests, though less critical).

### P2 (Consider)
1.  **Drop `te_run`:** If `te` is just a wrapper around other tools, consider removing it from MCP to reduce attack surface.
2.  **Add SAST to CI:** Run `bandit` and `semgrep` automatically on PRs.

## 6. Rem's Vicious Verdict

**"You built a fortress with a steel door (`run_cmd`), but left the window open (`te_run`). Typical. I found your weakness in less than 5 minutes. Fix it before the real demons come."**
