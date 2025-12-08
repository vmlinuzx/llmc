# Security Audit Report - Initial Assessment

**Date:** 2025-12-07
**Auditor:** Rem the Penetration Testing Demon
**Target:** `llmc` Codebase
**Focus:** Remote Code Execution (RCE), Command Injection, Isolation Bypass

## 1. Executive Summary

**Overall Risk: CRITICAL**

The `llmc` codebase contains multiple critical vulnerabilities that allow for **Arbitrary Code Execution (RCE)** and **Command Injection**. These vulnerabilities are trivial to exploit if an attacker can interact with the MCP server or provide input files to the RUTA testing framework.

The "isolation" security control intended to mitigate these risks relies on environment variables (`LLMC_ISOLATED`) which can be spoofed or simply do not exist if the user runs the tool directly on their host machine, leading to total system compromise.

**Critical Vulnerabilities Found:** 2 (Verified via PoC) + 1 (Code Analysis)
**Exploitability:** 5/5 (Trivial)

## 2. Threat Model

- **Assets:** User's filesystem, credentials, local network access.
- **Adversaries:**
    - Malicious actors controlling input to the MCP server (if exposed).
    - Attackers providing malicious RUTA scenario files (e.g., via shared repos).
- **Attack Vectors:**
    - **MCP Server:** Sending crafted commands to `run_cmd` or `execute_code`.
    - **RUTA:** Embedding Python payloads in Scenario YAML/JSON files.

## 3. Vulnerabilities Found

### VULN-001: Command Injection in MCP `run_cmd` tool
- **Severity:** **CRITICAL**
- **CWE:** CWE-78 (OS Command Injection)
- **Location:** `llmc_mcp/tools/cmd.py:run_cmd`
- **Description:** The `run_cmd` function uses `subprocess.run(..., shell=True)`. The validation logic only checks the *first* token of the command against a blacklist (which is empty by default). An attacker can chain commands using shell metacharacters (`;`, `&&`, `|`) to execute arbitrary commands.
- **Proof of Concept:**
  ```python
  # See tests/security/test_pocs.py
  run_cmd("ls ; touch /tmp/pwned", ...)
  ```
- **Remediation:**
    1.  **Remove `shell=True`**. Use `shlex.split()` and pass the list of arguments directly to `subprocess.run`.
    2.  Implement a strict **whitelist** of allowed binaries, not a blacklist.

### VULN-002: Arbitrary Code Execution in RUTA Judge
- **Severity:** **CRITICAL**
- **CWE:** CWE-95 (Improper Neutralization of Directives in Dynamically Evaluated Code)
- **Location:** `llmc/ruta/judge.py:_check_metamorphic`
- **Description:** The `Judge` class evaluates constraint strings from Scenario files using Python's `eval()`. The environment is not properly sandboxed, allowing access to `__builtins__` and arbitrary module imports.
- **Proof of Concept:**
  ```yaml
  # Malicious Scenario File
  expectations:
    properties:
      - name: exploit
        type: metamorphic
        constraint: "__import__('os').system('rm -rf /') == 0"
  ```
- **Remediation:**
    - Use `simpleeval` or `ast.literal_eval` for safe evaluation.
    - Completely avoid `eval()` for untrusted input.

### VULN-003: Weak Isolation Detection
- **Severity:** **HIGH**
- **CWE:** CWE-653 (Improper Isolation or Compartmentalization)
- **Location:** `llmc_mcp/isolation.py`
- **Description:** The system relies on checking environment variables (like `LLMC_ISOLATED`) or file existence (`/.dockerenv`) to determine if it is safe to run dangerous tools. This is a fragile check that doesn't guarantee actual security boundaries.
- **Remediation:**
    - Do not rely on "detection" for security.
    - **Enforce** sandboxing at the OS level (e.g., using `nsjail` or running inside a VM) regardless of flags.
    - If running on host, dangerous tools should be **disabled by default** with a prominent warning/confirmation required to enable them.

## 4. Other Findings

- **Hardcoded Secrets:** Several test files and documentation contain placeholder API keys (e.g., `sk-...`). While mostly harmless, `tests/REPORTS/ren_security_gaps_analysis.md` notes a hardcoded Gemini key in source history.
- **Dynamic SQL:** `tools/rag/database.py` and others construct SQL queries using f-strings (`ALTER TABLE {table}`). While not immediately exploitable without user control over table names, it is bad practice.

## 5. Recommendations

### Immediate Actions (P0)
1.  **Disable `shell=True`** in `llmc_mcp/tools/cmd.py` immediately.
2.  **Replace `eval()`** in `llmc/ruta/judge.py` with a safe expression evaluator.
3.  **Populate the Blacklist** in `llmc_mcp/tools/cmd.py` or switch to a Whitelist.

### Strategic Improvements (P1)
1.  **Rethink Isolation:** Instead of checking *if* we are isolated, the tool should *ensure* isolation (e.g., by spawning the tool execution inside a container/nsjail).
2.  **Input Sanitization:** Implement strict schema validation for all inputs to MCP tools.

## 6. Security Verdict

**VERDICT: FAIL**

The current state of `llmc` is **highly insecure** for production use or use on untrusted inputs. The MCP server acts as a "remote shell" with minimal protection, and the testing framework allows for arbitrary code execution via configuration files.

*Rem the Penetration Testing Demon*
