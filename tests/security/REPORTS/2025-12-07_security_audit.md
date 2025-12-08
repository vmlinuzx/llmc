# Security Audit Report - LLMC Codebase
**Date:** 2025-12-07
**Auditor:** Rem the Penetration Testing Demon

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Server (Network/Local), RUTA Scenario Files (File System), CLI Arguments.
- **Critical Vulnerabilities Found:** 2 (Verified RCEs)
- **Exploitability:** High (5/5) - Trivial payloads, default configurations insecure.

The audit identified two confirmed Remote Code Execution (RCE) vulnerabilities. One in the `RUTA` evaluation engine allowing arbitrary Python code execution via scenario files, and another in the `MCP` server allowing Command Injection via shell metacharacters despite "validation" attempts.

## 2. Threat Model
- **Assets:** Host system access, sensitive data in RAG index, internal network access (via MCP).
- **Adversaries:** 
    - Malicious MCP client (e.g., compromised LLM or user interface).
    - Attacker supplying malicious RUTA scenario files (e.g., via shared repo).
- **Trust Boundaries:** 
    - **MCP:** Untrusted input -> `run_cmd` -> Shell Execution.
    - **RUTA:** Untrusted Scenario YAML -> `Judge` -> `eval()`.

## 3. Vulnerabilities Found

### VULN-001: Arbitrary Code Execution in RUTA Judge
- **Severity:** **CRITICAL**
- **CWE:** CWE-95 (Improper Neutralization of Directives in Dynamically Evaluated Code)
- **Location:** `llmc/ruta/judge.py:136`, `llmc/ruta/judge.py:146`
- **Description:** The `Judge` class uses Python's built-in `eval()` function to evaluate scenario properties (`relation` and `constraint`). These strings are taken directly from the scenario object without sanitization.
- **Impact:** Full Remote Code Execution (RCE). An attacker can supply a malicious scenario file that executes arbitrary system commands when loaded by the test runner.
- **Proof of Concept:** `tests/security/exploit_ruta_eval.py`
  ```python
  # Payload
  constraint = "__import__('os').system('id')"
  ```
- **Remediation:**
  - **Immediate:** Replace `eval()` with `ast.literal_eval()` (if only literals needed) or use a safe expression evaluation library like `simpleeval` or `asteval`.
  - **Never** use `eval()` on data that could originate from external sources.

### VULN-002: Command Injection in MCP `run_cmd`
- **Severity:** **HIGH**
- **CWE:** CWE-78 (OS Command Injection)
- **Location:** `llmc_mcp/tools/cmd.py:104`
- **Description:** The `run_cmd` function uses `subprocess.run(..., shell=True)`. The `validate_command` function attempts to restrict execution by checking only the *first* token of the command against a blacklist. This logic is flawed because `shell=True` executes the entire string. An attacker can chain commands (e.g., `echo allowed; malicious_cmd`) to bypass the check.
- **Impact:** Arbitrary Command Execution. While `require_isolation` attempts to mitigate impact, the vulnerability allows full compromise of the container/sandbox. If isolation is misconfigured or bypassed, it compromises the host.
- **Proof of Concept:** `tests/security/exploit_mcp_cmd_injection.py`
  ```python
  # Payload passes validation (starts with 'echo') but executes 'whoami'
  run_cmd("echo hello; whoami", shell=True)
  ```
- **Remediation:**
  - **Fix Validation:** Do not rely on parsing command strings yourself.
  - **Disable Shell:** Use `shell=False` and pass arguments as a list.
  - **Sanitization:** If `shell=True` is absolutely necessary (rare), strictly whitelist allowed characters (alphanumeric only).

### VULN-003: Weak Isolation Detection
- **Severity:** Low (Defense in Depth)
- **Location:** `llmc_mcp/isolation.py`
- **Description:** Isolation detection relies on checking for file existence (`/.dockerenv`) or environment variables. These can be spoofed or hidden.
- **Remediation:** Use stronger checks if possible, but primarily fix the underlying vulnerabilities so reliance on isolation is reduced.

## 4. Security Strengths
- **Isolation Check:** The `require_isolation` hook in `run_cmd` is a good defense-in-depth measure (prevented the PoC from running on bare metal without manual bypass).
- **Code Execution Mode:** The "Code Execution" tool (`llmc_mcp/tools/code_exec.py`) appears to use a stub-based approach which reduces the attack surface compared to passing raw code to `exec` (though the generated stubs need review).

## 5. Recommendations (Prioritized)

### P0 (Fix Before Production)
1.  **Refactor RUTA Judge:** Rewrite `llmc/ruta/judge.py` to remove `eval()`. Use a dedicated DSL parser.
2.  **Fix `run_cmd`:** Change `run_cmd` to use `shell=False`.
    ```python
    # Secure pattern
    subprocess.run([binary] + args, shell=False)
    ```
    If `shell=True` is required for pipes/redirection, use a strictly controlled execution wrapper or explicit `subprocess.Popen` chaining.

### P1 (Fix Soon)
1.  **Empty Blacklist:** Populate `DEFAULT_BLACKLIST` in `llmc_mcp/tools/cmd.py` with dangerous binaries (`rm`, `dd`, `nc`, `bash`, `python`, etc.) if the tool is intended to be restricted.
2.  **Secrets Management:** Remove hardcoded API key placeholders from `tools/rag/enrichment_adapters/` to prevent accidental commit of real keys.

## 6. Rem's Vicious Security Verdict
I have ripped your "defenses" to shreds. A trivial `;` destroyed your command validation, and `eval()`? In 2025? Pathetic. Fix these holes before I return with the `rm -rf /` payload.
