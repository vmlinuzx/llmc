# Security Audit Report - LLMC MCP Server

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Server Tools (`execute_code`, `run_cmd`, `fs`)
- **Critical Vulnerabilities Found:** 2 (RCE, Command Injection)
- **Exploitability:** 5/5 (Trivial, enabled by default)

The LLMC MCP Server contains **multiple critical vulnerabilities** that allow a malicious actor (or a rogue LLM) to execute arbitrary code and system commands on the host machine. These features are **enabled by default** in the repository configuration (`llmc.toml`), making the out-of-the-box installation immediately vulnerable.

## 2. Threat Model
- **Assets:** Host filesystem, User data, Environment variables (Secrets).
- **Adversaries:** Malicious LLM prompts, Compromised MCP clients, Users running untrusted configurations.
- **Attack Vectors:**
    1.  **Direct Tool Use:** The `execute_code` tool allows arbitrary Python execution.
    2.  **Command Injection:** The `run_cmd` tool allows shell command execution with trivial bypasses.
    3.  **Path Traversal:** File system tools rely on configuration that defaults to broad access.

## 3. Vulnerabilities Found

### VULN-001: Unrestricted Remote Code Execution (RCE)
- **Severity:** **CRITICAL**
- **CWE:** CWE-94 (Improper Control of Generation of Code)
- **Attack Vector:** Call `execute_code` tool with Python payload.
- **Impact:** Full system compromise. Attacker can read/write files, steal secrets, and install malware.
- **Affected Code:** `llmc_mcp/tools/code_exec.py:277` (`exec(compiled, namespace)`)
- **Proof of Concept:**
  ```python
  execute_code(code="import os; os.system('id > /tmp/pwned')", ...)
  ```
- **Remediation:**
  1.  **Disable by default.**
  2.  **Sandbox Execution:** Do not use `exec()` in the host process. Use a container (Docker) or lightweight sandbox (nsjail/Firejail).
  3.  **Restrict Imports:** If running locally, strictly limit available modules (e.g., using `RestrictedPython`), though this is rarely sufficient.

### VULN-002: Command Injection & Blacklist Bypass
- **Severity:** **CRITICAL**
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** Call `run_cmd` with chained commands or blocked binaries.
- **Impact:** Arbitrary shell command execution.
- **Affected Code:** `llmc_mcp/tools/cmd.py` (uses `shell=True`) and `llmc.toml` (Configuration mismatch).
- **Details:**
    - The code implements a **blacklist** approach (`run_cmd_blacklist`), which is notoriously insecure.
    - The configuration (`llmc.toml`) defines a `run_cmd_allowlist`, but the code in `config.py` looks for `run_cmd_blacklist`. This mismatch results in an **empty blacklist**, allowing all commands.
    - Even with a blacklist, `shell=True` allows chaining (e.g., `echo safe; rm -rf /`).
- **Remediation:**
  1.  **Use `shell=False`:** Pass arguments as a list.
  2.  **Enforce Strict Allowlist:** Only allow specific, parameterized commands.
  3.  **Fix Config Mismatch:** Ensure code respects the allowlist defined in TOML.

### VULN-003: Insecure Default Configuration
- **Severity:** **HIGH**
- **CWE:** CWE-1188 (Insecure Default Initialization of Resource)
- **Impact:** Immediate exposure of critical vulnerabilities upon installation.
- **Details:**
    - `llmc.toml` sets `mcp.code_execution.enabled = true`.
    - `llmc.toml` sets `mcp.tools.enable_run_cmd = true`.
    - `llmc_mcp/tools/fs.py` defaults to full filesystem access if `allowed_roots` is empty (though `llmc.toml` sets it to repo root).
- **Remediation:**
  - Set all dangerous features to `false` in default config.
  - Require explicit user opt-in for `execute_code` and `run_cmd`.

### VULN-004: Potential Eval Injection in RUTA
- **Severity:** **MEDIUM**
- **CWE:** CWE-95 (Improper Neutralization of Directives in Dynamically Evaluated Code)
- **Affected Code:** `llmc/ruta/judge.py:136` (`eval(prop.relation, {}, context)`)
- **Details:** `eval()` is used to evaluate logic. If the expression is derived from LLM output or user input without strict sanitization, it poses an RCE risk.
- **Remediation:** Use `ast.literal_eval` or a specialized expression parser (e.g., `simpleeval`).

## 4. Security Strengths
- **Subprocess Usage:** Most internal tools (git, etc.) use `subprocess.run` with `shell=False` (list of args), which prevents command injection in those specific areas.
- **Type Hints:** The codebase uses strong typing, which helps in static analysis.

## 5. Recommendations (Prioritized)

### P0 (Immediate Fix)
1.  **Disable `execute_code` and `run_cmd` in `llmc.toml`.**
2.  **Patch `llmc_mcp/tools/cmd.py`:** Remove `shell=True` and implement strict allowlisting.
3.  **Patch `llmc_mcp/tools/code_exec.py`:** Add a warning or require a strictly isolated environment.

### P1 (Soon)
1.  **Fix Config Loading:** Resolve the `allowlist` vs `blacklist` bug in `llmc_mcp/config.py`.
2.  **Audit `eval()`:** Replace `eval()` in `llmc/ruta/judge.py` with safer alternatives.
3.  **Dependency Scanning:** Add `pip-audit` to CI/CD or pre-commit hooks.

### P2 (Hardening)
1.  **Docker Sandbox:** Implement the `docker` sandbox mode referenced in `config.py`.
2.  **Least Privilege:** Ensure the MCP server runs with minimal filesystem permissions.

## 6. Security Test Coverage
- **Tested:** `execute_code`, `run_cmd`, `fs` tools.
- **Verified:** RCE, Command Injection, Config defaults.
- **Not Tested:** Authentication (Token mode), Network-based attacks (HTTP transport), DoS limits.

## 7. Rem's Vicious Security Verdict
**"You handed me the keys to the kingdom, Dave. I didn't even have to break the lock; I just turned the handle. 5/5 Stars for 'Ease of Exploitation'."**
