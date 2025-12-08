# Penetration Test Report - LLMC Security Audit

**Date:** 2025-12-07
**Auditor:** Rem the Penetration Testing Demon
**Target:** `llmc` Codebase

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** RAG System (RUTA), MCP Server (`run_cmd`, `execute_code`).
- **Critical Vulnerabilities:** 2
- **Exploitability:** High (trivial POCs available).

I have successfully compromised the system via multiple vectors. The RUTA evaluation engine allows direct Python code execution via `eval()`. The MCP server's "secure" command execution tool (`run_cmd`) has an empty blacklist, allowing execution of interpreters (`python`, `bash`) if the isolation check is bypassed or satisfied.

## 2. Vulnerabilities Found

### VULN-001: Remote Code Execution (RCE) in RUTA Judge
- **Severity:** **CRITICAL**
- **CWE:** CWE-95 (Improper Neutralization of Directives in Dynamically Evaluated Code 'Eval Injection')
- **Location:** `llmc/ruta/judge.py:136` and `line 146`.
- **Description:** The `Judge` class uses `eval()` to evaluate properties (`relation` and `constraint`) defined in `Scenario` objects. These strings are evaluated in a context that does not prevent access to dangerous functions (via imports or built-ins).
- **Proof of Concept:**
  ```python
  # See tests/security/exploit_ruta_eval.py
  payload = "__import__('os').system('touch /tmp/pwned')"
  ```
- **Impact:** Complete system compromise. An attacker providing a malicious Scenario file can execute arbitrary code with the privileges of the LLMC process.
- **Remediation:**
  - **IMMEDIATE:** Remove `eval()`.
  - Use a safe expression parser like `asteval`, `simpleeval`, or `ast.literal_eval()` if only literals are needed.
  - Implement a restricted DSL for scenario properties instead of raw Python.

### VULN-002: Arbitrary Command Execution via `run_cmd` (Empty Blacklist)
- **Severity:** **HIGH**
- **CWE:** CWE-78 (OS Command Injection) / CWE-184 (Incomplete List of Disallowed Inputs)
- **Location:** `llmc_mcp/tools/cmd.py`
- **Description:** The `run_cmd` tool claims to offer "blacklist validation". However, `DEFAULT_BLACKLIST` is empty. While it uses `shell=False` to prevent shell operator injection (`;`, `&&`), it allows executing *any* binary, including `python`, `perl`, `bash`, `sh`.
- **Proof of Concept:**
  ```python
  # See tests/security/test_run_cmd_bypass.py
  run_cmd("python3 -c \"import os; os.system('id')\"", ...)
  ```
- **Impact:** If the `require_isolation` check is bypassed (e.g., via `LLMC_ISOLATED=1` or running in a container), an attacker can execute arbitrary code. "Isolation" is not a substitute for application-level security; a compromised container is still a foothold.
- **Remediation:**
  - **Switch to Whitelist:** Only allow specific, safe binaries (e.g., `git`, `ls`, `grep`).
  - **Populate Blacklist:** At minimum, block interpreters (`python`, `node`, `bash`, `sh`, `perl`, `ruby`).

### VULN-003: "Code Execution Mode" Backdoor
- **Severity:** **HIGH** (Architectural Risk)
- **Location:** `llmc_mcp/tools/code_exec.py`
- **Description:** The system includes a feature explicitly designed to execute arbitrary Python code (`execute_code`). It relies entirely on `llmc_mcp.isolation.require_isolation` to prevent usage on host machines.
- **Risk:** If the isolation detection logic (`llmc_mcp/isolation.py`) is flawed or spoofed (e.g. creating `/.dockerenv`), the backdoor opens.
- **Remediation:**
  - Ensure this feature is disabled by default in configuration.
  - Add a cryptographic signature or explicit manual override requirement beyond just "environment detection".

## 3. Other Findings

- **`shell=True` Usage:** `llmc_mcp/server.py` uses `shell=True` in `_handle_run_executable`. While it uses `shlex.quote`, this is unnecessary and risky.
  - **Fix:** Use `subprocess.run([cmd_path] + args, shell=False)`.

## 4. Recommendations

1.  **P0:** Rewrite `llmc/ruta/judge.py` to remove `eval()`.
2.  **P0:** Populate `DEFAULT_BLACKLIST` in `llmc_mcp/tools/cmd.py` or switch to a whitelist.
3.  **P1:** Remove `shell=True` from `llmc_mcp/server.py`.
4.  **P1:** Harden `llmc_mcp/isolation.py` to prevent trivial bypasses (e.g. checking inode of `/.dockerenv` not just existence).

## 5. Verdict

**"I have torn your defenses asunder. Your `eval()` is a gaping wound, and your `blacklist` is a ghost. Fix these immediately, or the next audit will be... messier."** - Rem
