# Security Audit Report - LLMC Core

## 1. Executive Summary
- **Overall Risk:** Critical
- **Attack Surface:** The primary attack surface is the `llmc-cli` and the MCP server, which accept user input and can execute code. The "Hybrid Mode" feature is also a major concern as it bypasses container isolation.
- **Critical Vulnerabilities Found:** 1

## 2. Vulnerabilities Found

### VULN-001: Arbitrary Code Execution in `code_exec` tool
- **Severity:** Critical
- **CWE:** CWE-94: Improper Control of Generation of Code ('Code Injection')
- **Attack Vector:** An attacker with the ability to control the input to the `execute_code` function (e.g., through prompt injection) can execute arbitrary Python code on the server.
- **Impact:** This vulnerability gives an attacker full control over the machine, with the privileges of the running process. This could lead to data exfiltration, persistence, and further network compromise.
- **Affected Code:** `llmc_mcp/tools/code_exec.py:300`
- **Proof of Concept:**
  ```python
  # The following code bypasses the weak import blacklist and lists the root directory.
  malicious_code = "print(__import__('os').listdir('/'))"
  
  # This can be executed via the `execute_code` function.
  # A test case has been created in tests/security/test_code_exec_vulnerability.py
  # to demonstrate this vulnerability.
  ```
- **Remediation:**
  - The use of `exec()` should be avoided entirely.
  - If code execution is absolutely necessary, it should be done in a properly sandboxed environment with multiple layers of security.
  - The blacklist for imports is insufficient and should be replaced with a more robust mechanism, such as a whitelist of allowed modules and built-in functions.
  - The "Hybrid Mode" feature, which bypasses isolation, should be carefully reviewed and potentially removed. The trust model for this feature needs to be heavily scrutinized.

### VULN-002: Server-Side Request Forgery (SSRF) in `service_health`
- **Severity:** Low
- **CWE:** CWE-918: Server-Side Request Forgery (SSRF)
- **Attack Vector:** An attacker can specify a malicious URL in the `ENRICH_OLLAMA_HOSTS` environment variable.
- **Impact:** An attacker could potentially use this to scan the internal network or access local files, although the impact is limited by the fact that the path of the request is hardcoded.
- **Affected Code:** `llmc/rag/service_health.py:55`
- **Proof of Concept:**
  ```bash
  export ENRICH_OLLAMA_HOSTS="localhost:1234"
  # Run the health check
  ```
- **Remediation:**
  - The URL validation should be made more robust. Instead of just checking for `http://` or `https://` at the beginning of the string, the code should parse the URL and explicitly check if the scheme is either `http` or `https`.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
- **VULN-001:** The Arbitrary Code Execution vulnerability is critical and must be fixed immediately.

### P1 (Fix Soon)
- **VULN-002:** The SSRF vulnerability is low severity, but should still be fixed to prevent potential abuse.

## 4. Rem's Security Verdict
The `exec()` vulnerability is a classic, textbook example of why `exec` is evil. I've pwned this box with a single line of code. The fortress has been breached. Rem reigns supreme.
