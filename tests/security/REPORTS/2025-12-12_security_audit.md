# Security Audit Report - LLMC Codebase
**Date:** 2025-12-12
**Auditor:** Rem the Penetration Testing Demon

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** CLI (`te`), MCP Server, RUTA Evaluation
- **Critical Vulnerabilities Found:** 1
- **High Vulnerabilities Found:** 1
- **Exploitability:** 5/5 (Trivial)

The codebase contains a **CRITICAL** command injection vulnerability in the Tool Envelope (`te`) CLI that allows arbitrary code execution. The MCP server also employs unsafe practices (`shell=True`) which, while currently mitigated by `shlex`, represents a significant risk.

## 2. Threat Model
- **Assets:** User filesystem, RAG database, API keys.
- **Adversaries:** Malicious users, compromised LLM outputs (prompt injection leading to tool misuse).
- **Attack Vectors:**
    - CLI arguments to `te`
    - JSON payloads to MCP server
    - YAML scenarios for RUTA

## 3. Vulnerabilities Found

### VULN-001: Command Injection in `te` CLI
- **Severity:** **CRITICAL**
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:**
    The `_handle_passthrough` function in `llmc/te/cli.py` concatenates command arguments into a single string and executes them using `subprocess.run(..., shell=True)`.
- **Impact:** Full Remote Code Execution (RCE) as the user running the CLI.
- **Affected Code:** `llmc/te/cli.py:404`
- **Proof of Concept:**
  ```bash
  # Execute 'ls', then execute 'echo PWNED'
  te ls "; echo PWNED"
  ```
  See `tests/security/test_te_injection.py` for automated PoC.
- **Remediation:**
  Do NOT use `shell=True`. Pass the list of arguments directly to `subprocess.run`.
  ```python
  # Vulnerable
  full_cmd = " ".join([command] + args)
  subprocess.run(full_cmd, shell=True, ...)

  # Fixed
  subprocess.run([command] + args, shell=False, ...)
  ```

### VULN-002: Unsafe Shell Execution in MCP Server
- **Severity:** **HIGH**
- **CWE:** CWE-78 / CWE-88
- **Attack Vector:**
    The `_handle_run_executable` method in `llmc_mcp/server.py` uses `shell=True` to run executables. While it uses `shlex.quote`, this is fragile and unnecessary.
- **Impact:** Potential RCE if `shlex` quoting is bypassed or if the executable name itself is user-controlled and unvalidated.
- **Affected Code:** `llmc_mcp/server.py:888` (approx)
- **Proof of Concept:**
  See `tests/security/test_mcp_shell.py`.
- **Remediation:**
  Remove `shell=True` and `shlex.quote`. Pass the list of arguments directly.
  ```python
  # Vulnerable
  full_cmd = f"{shlex.quote(cmd_path)} {' '.join(quoted_args)}"
  subprocess.run(full_cmd, shell=True, ...)

  # Fixed
  subprocess.run([cmd_path] + args, shell=False, ...)
  ```

### VULN-003: Default Sandbox Configuration
- **Severity:** **MEDIUM**
- **Attack Vector:**
    `llmc_mcp/config.py` defaults `sandbox` to "subprocess".
- **Impact:** Code execution runs on the host system by default.
- **Remediation:**
    Change default to "nsjail" or "docker", or enforce a warning if "subprocess" is used.

## 4. Security Strengths
- **RUTA Eval:** The `_safe_eval` implementation in `llmc/ruta/judge.py` correctly uses `simpleeval` to prevent arbitrary code execution via `eval()`. Attempts to use `__import__` or `os.system` are blocked.
- **Secrets:** No hardcoded API keys were found in the codebase.

## 5. Recommendations
### P0 (Fix Immediately)
1.  **Refactor `llmc/te/cli.py`**: Remove `shell=True` immediately. This is a trivial exploit.
2.  **Refactor `llmc_mcp/server.py`**: Remove `shell=True` from `_handle_run_executable`.

### P1 (Fix Soon)
1.  **Harden Config**: Change default sandbox to a safer option or require explicit opt-in for "subprocess".
2.  **Input Validation**: Add strict validation for `cmd_path` in MCP server.

## 6. Security Test Coverage
- **Tested:**
    - `te` CLI argument handling (PoC verified)
    - `ruta` evaluation logic (PoC verified safe)
    - `llmc_mcp` server execution logic (PoC verified shell usage)
- **Not Tested:**
    - RAG database SQL injection (time constraints)
    - Network fuzzing of MCP server

## 7. Rem's Verdict
The system is **wide open**. The `te` CLI is a welcome mat for attackers. Fix VULN-001 or prepare for total compromise.
