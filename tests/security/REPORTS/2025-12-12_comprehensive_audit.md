# Security Audit Report - Comprehensive Codebase Audit

**Date:** 2025-12-12
**Auditor:** Rem the Penetration Testing Demon

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** CLI Tools (`te`, `llmc-cli`), MCP Server, RAG Backend.
- **Critical Vulnerabilities Found:** 2 (RCE confirmed).
- **Exploitability:** 5/5 (Trivial command injection).

The system contains a **Critical Remote Code Execution (RCE)** vulnerability in the `te` (Tool Envelope) CLI, which is exposed via the MCP server. An attacker can execute arbitrary shell commands by injecting shell metacharacters into the arguments. Additionally, the RAG backend is vulnerable to argument injection.

## 2. Threat Model
- **Assets:** Codebase access, System shell, Environment variables (Secrets).
- **Adversaries:** Malicious MCP clients, untrusted RAG queries, compromised agents.
- **Trust Boundaries:** 
    - `te` CLI input (Trusts all args -> Shell).
    - `llmc_agent` RAG query (Trusts query -> Subprocess).
    - `MCP` server (Relies on `te` for execution).

## 3. Vulnerabilities Found

### VULN-001: RCE via Command Injection in Tool Envelope (TE)
- **Severity:** **CRITICAL**
- **CWE:** CWE-78 (OS Command Injection)
- **Affected Code:** `llmc/te/cli.py:402`
- **Description:** The `_handle_passthrough` function constructs a shell command by concatenating arguments with spaces and executing it with `subprocess.run(..., shell=True)`.
- **Impact:** Full system compromise. An attacker can execute arbitrary commands with the privileges of the user running `te` (or the MCP server).
- **Proof of Concept:**
  ```python
  from llmc.te.cli import _handle_passthrough
  # Executes 'echo pwned'
  _handle_passthrough("run", ["; echo pwned"], Path("."))
  ```
- **Remediation:**
  1.  **Remove `shell=True`**.
  2.  Pass arguments as a list directly to `subprocess.run`.
  ```python
  # Fix
  subprocess.run([command] + args, shell=False, ...)
  ```

### VULN-002: Argument Injection in LLMC Agent Backend
- **Severity:** **HIGH**
- **CWE:** CWE-88 (Argument Injection)
- **Affected Code:** `llmc_agent/backends/llmc.py`
- **Description:** User-provided queries are passed directly to `rg` (ripgrep) and `llmc-cli` subprocesses without the `--` delimiter. Queries starting with `-` are interpreted as flags.
- **Impact:** An attacker can inject flags to alter tool behavior (e.g., write to files, change output format, denial of service).
- **Proof of Concept:**
  ```python
  # Pass "--help" as query -> rg prints help instead of searching
  backend.search("--help")
  ```
- **Remediation:**
  Insert `--` before the query argument.
  ```python
  subprocess.run(["rg", ..., "--", query])
  ```

### VULN-003: Unnecessary `shell=True` in MCP Server
- **Severity:** **MEDIUM**
- **Affected Code:** `llmc_mcp/server.py:885`
- **Description:** `_handle_run_executable` uses `shell=True`. While it uses `shlex.quote`, this is defensive coding that relies on correct quoting behavior.
- **Remediation:** Use `shell=False` and pass the command list `[cmd_path] + args`.

### VULN-004: Weak Isolation Enforcement
- **Severity:** **MEDIUM**
- **Affected Code:** `llmc_mcp/isolation.py`
- **Description:** Isolation checks can be bypassed by setting `LLMC_ISOLATED=1`. While useful for testing, this could be abused if an attacker can influence environment variables.
- **Remediation:** Log a loud warning when this bypass is used. Ensure production environments strip this variable.

## 4. Security Strengths
- **RUTA Eval:** The `Judge` class uses `simpleeval` with a whitelist, effectively mitigating Python Code Injection and simple DoS attacks (as verified by POC).
- **Cmd Tool:** `llmc_mcp/tools/cmd.py` correctly uses `shell=False` and supports a binary blacklist.

## 5. Recommendations (Prioritized)

### P0 (Immediate Fix)
1.  **Patch `llmc/te/cli.py`:** Switch to `shell=False` immediately. This is an open door for RCE.
2.  **Patch `llmc_agent/backends/llmc.py`:** Add `--` delimiter to all subprocess calls accepting user input.

### P1 (High Priority)
1.  **Remove `shell=True`** from `llmc_mcp/server.py`.
2.  **Harden `te`:** Ensure it strictly validates commands if it must act as a wrapper.

### P2 (Defense in Depth)
1.  **Populate Blacklist:** The default blacklist in `llmc_mcp/tools/cmd.py` is empty. Add dangerous binaries (`nc`, `curl`, `wget`, `python`, `perl`, `bash`, `sh`).
2.  **Sandboxing:** Enforce `nsjail` or similar for `execute_code` at the OS level, not just Python level checks.

## 6. Conclusion
The codebase has significantly improved in some areas (RUTA `simpleeval`), but the introduction of the `te` tool created a massive security hole. The reliance on `shell=True` in a utility meant to be a wrapper is a classic mistake. Fix VULN-001 immediately.

**"You built a castle with a drawbridge made of paper. I burned it down with a single match."** - Rem
