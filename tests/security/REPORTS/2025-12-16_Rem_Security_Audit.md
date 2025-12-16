# Security Audit Report - LLMC MCP Server & LinuxOps

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Tools (`linux_proc_start`, `run_cmd`), Hybrid Mode Configuration
- **Critical Vulnerabilities Found:** 2
- **Exploitability:** 5/5 (Trivial RCE)

The LLMC MCP Server contains **two critical Remote Code Execution (RCE)** vulnerabilities that allow an attacker (or a confused LLM) to execute arbitrary commands on the host system. These vulnerabilities exist in both "Classic" and the new "Hybrid" modes. The "isolation" mechanisms are either completely missing for certain tools or explicitly bypassed in Hybrid Mode without adequate replacement controls.

## 2. Threat Model
- **Assets:** Host filesystem, User credentials, Environment variables, Network access.
- **Adversaries:** Malicious MCP clients, Prompt Injection attacks controlling the LLM, Compromised agents.
- **Attack Vectors:**
    1.  Calling `linux_proc_start` with `bash` (Classic Mode).
    2.  Calling `run_cmd` with arbitrary commands (Hybrid Mode).
- **Trust Boundaries:** The MCP server interface is the primary trust boundary. Input from the LLM/Client is treated as semi-trusted in Hybrid Mode, which is a fatal design flaw given the lack of validation.

## 3. Vulnerabilities Found

### VULN-001: Unrestricted RCE via `linux_proc_start` (Classic Mode)
- **Severity:** **Critical**
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** `linux_proc_start` tool
- **Impact:** Full Remote Code Execution as the user running the MCP server.
- **Affected Code:** `llmc_mcp/tools/linux_ops/proc.py:mcp_linux_proc_start`
- **Description:** The `linux_proc_start` tool is enabled by default (`repl_enabled=True` in `LinuxOpsConfig`). It accepts a `command` argument which is passed directly to `subprocess.Popen` (via `start_process`). Unlike `run_cmd`, it performs **NO blacklist checks** and **NO isolation checks**.
- **Proof of Concept:**
  ```python
  # See tests/security/poc_repl_rce.py
  start_process(command="bash")
  send_input(proc_id, "cat /etc/passwd")
  ```
- **Remediation:**
  1.  Disable `repl_enabled` by default.
  2.  Enforce `require_isolation` for `linux_proc_start`.
  3.  Implement a strict whitelist for allowed REPL binaries (e.g., only `python`, `node` if strictly necessary, but `bash` should likely be banned).

### VULN-002: Command Injection via `run_cmd` in Hybrid Mode
- **Severity:** **Critical**
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** `run_cmd` tool
- **Impact:** Full Remote Code Execution on the host.
- **Affected Code:** `llmc_mcp/tools/cmd.py:run_cmd` and `llmc_mcp/server.py`
- **Description:** In "Hybrid Mode" (`mode="hybrid"`), the `run_cmd` tool is promoted to a first-class tool. The server sets `host_mode=True`, which explicitly **bypasses** the `require_isolation` check. The default blacklist is **empty**, allowing execution of any command.
- **Proof of Concept:**
  ```python
  # See tests/security/poc_hybrid_run_cmd.py
  run_cmd(command="id", host_mode=True)
  ```
- **Remediation:**
  1.  Do not bypass isolation in Hybrid Mode unless a very strict whitelist is in place.
  2.  Populate `DEFAULT_BLACKLIST` with dangerous binaries (`bash`, `sh`, `rm`, `nc`, etc.).
  3.  Ideally, `run_cmd` should NEVER run on the host without a confirmation prompt or restricted scope.

## 4. Security Strengths
- **Path Traversal Protection:** `llmc_mcp/tools/fs.py` implements robust path validation using `pathlib.resolve()` and checks against `allowed_roots`.
- **Isolation Check:** The `require_isolation` function exists and checks for container environments, although it can be bypassed if the attacker has env var control (but good for defense-in-depth).

## 5. Missing Security Controls
- **Input Validation:** No validation on `linux_proc_start` command argument.
- **Least Privilege:** MCP server runs with user privileges; RCE exposes full user access.
- **Defense in Depth:** Hybrid Mode removes the primary defense (isolation) without adding a secondary defense (sandbox/strict whitelist).

## 6. Recommendations (Prioritized)

### P0 (Fix Before Production)
1.  **Hard-Disable `linux_proc_start`** unless explicitly enabled by user AND isolated.
2.  **Remove `host_mode` bypass** in `run_cmd` or enforce a strict **Whitelist** (not blacklist) for Hybrid Mode.
3.  **Audit `repl_enabled` default:** Change default to `False`.

### P1 (Fix Soon)
1.  Implement `AppArmor`/`SELinux` profiles for the MCP server.
2.  Add audit logging for all executed commands (even successful ones).

## 7. Security Test Coverage
- **Tested:** `linux_proc_start`, `run_cmd`, `fs` tools (static analysis).
- **Not Tested:** RAG SQL injection (time constraints), HTTP transport auth (focused on stdio).

## 8. Rem's Vicious Security Verdict
"Hybrid Mode" is currently "Suicide Mode". You are handing the LLM a loaded gun pointing at your foot. The `linux_proc_start` tool is a backdoor left wide open by default. Fix this immediately or don't complain when your `/home` gets wiped.
