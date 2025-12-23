# Security Audit Report - llmc

## 1. Executive Summary
- **Overall Risk:** High
- **Attack Surface:** The primary attack surface is the `llmc` command-line interface and the files it consumes, particularly those in the `.llmc` directory. An attacker with even limited access to the file system where the `llmc` repository is stored can introduce malicious files that lead to code execution or information disclosure.
- **Critical Vulnerabilities Found:** 4

## 2. Vulnerabilities Found

### VULN-001: Path Traversal in `_read_snippet`
- **Severity:** High
- **CWE:** CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
- **Attack Vector:** An attacker with write access to `.llmc/rag_graph.json` can create a malicious graph file. When a user runs a command that triggers the `_read_snippet` function (e.g., `llmc search`), the application will read arbitrary files from the filesystem.
- **Impact:** An attacker can read any file on the filesystem that the user running the `llmc` application has read access to. This could include sensitive files like `/etc/passwd`, SSH keys, or application source code.
- **Affected Code:** `llmc/rag_nav/tool_handlers.py` in the `_read_snippet` function.
- **Proof of Concept:**
  ```python
  # See tests/security/VULN-001/test_vuln_001.py
  # 1. Create a malicious .llmc/rag_graph.json:
  # {
  #     "nodes": [
  #         {
  #             "id": "malicious_node",
  #             "name": "malicious_node",
  #             "path": "/etc/passwd",
  #             "span": { "start_line": 1, "end_line": 2 }
  #         }
  #     ]
  # }
  # 2. Call a function that uses _read_snippet, for example by searching for 'malicious_node'.
  # The application will read and display the contents of /etc/passwd.
  ```
- **Remediation:**
  The `path` variable in `_read_snippet` should be validated to ensure it is a relative path that does not escape the `repo_root`. `os.path.join` should be avoided for joining untrusted paths. Instead, resolve and normalize the path and check that it is within the `repo_root`.

### VULN-002: Code Injection via `eval()` in RUTA Judge (Patched)
- **Severity:** Critical (Patched)
- **CWE:** CWE-94: Improper Control of Generation of Code ('Code Injection')
- **Attack Vector:** A specially crafted `constraint` in a RUTA scenario could lead to arbitrary code execution via the `eval()` function.
- **Impact:** Remote code execution.
- **Affected Code:** `llmc/ruta/judge.py` (prior to the fix)
- **Remediation:** The vulnerability has been patched by replacing the built-in `eval()` with the safer `simpleeval.EvalWithCompoundTypes` and whitelisting a small set of safe functions. This is a good example of a successful remediation.

### VULN-003: Hardcoded Test API Key
- **Severity:** Low
- **CWE:** CWE-798: Use of Hard-coded Credentials
- **Attack Vector:** An attacker with access to the source code could see the test key.
- **Impact:** Very low. The key is a fake test key (`sk-test`).
- **Affected Code:** `tests/test_wrapper_scripts.py`, `tests/test_e2e_operator_workflows.py`
- **Remediation:** Remove the hardcoded test key and use a mechanism like environment variables or a test-specific configuration file to provide the key during tests.

### VULN-004: Vulnerable Dependency `urllib3`
- **Severity:** Medium
- **CWE:** CWE-1104: Use of Unmaintained or Vulnerable Third-Party Components
- **Attack Vector:** An attacker could potentially exploit one of the vulnerabilities in `urllib3==2.3.0` if the application makes HTTP requests to a malicious server.
- **Impact:** Potential for various attacks, including Denial of Service or information leakage, depending on the nature of the vulnerabilities.
- **Affected Code:** The entire application is potentially affected, as `urllib3` is a fundamental dependency. The identified vulnerabilities are CVE-2025-50182, CVE-2025-50181, CVE-2025-66418, and CVE-2025-66471.
- **Remediation:** Upgrade `urllib3` to the latest version (at least 2.6.0) in `requirements.txt`.

### VULN-005: Potential SSRF / LFI via `urlopen`
- **Severity:** Medium
- **CWE:** CWE-918: Server-Side Request Forgery (SSRF) / CWE-22: Path Traversal
- **Attack Vector:** An attacker who can control the URL passed to `urllib.request.urlopen` could potentially make the application make requests to arbitrary internal or external services, or read local files using the `file:/` scheme.
- **Impact:** Information disclosure of local files or scanning of the internal network.
- **Affected Code:** `llmc/commands/repo_validator.py`, `llmc/rag/embeddings/check.py`, `llmc/rag/service_health.py`
- **Remediation:** The URLs passed to `urlopen` should be validated to ensure they are not pointing to internal services or local files. Implement a whitelist of allowed domains or schemes.

### VULN-006: Unpinned Hugging Face Model Download
- **Severity:** Medium
- **CWE:** CWE-494: Download of Code Without Integrity Check
- **Attack Vector:** An attacker who compromises the Hugging Face model repository could inject malicious code into the model.
- **Impact:** The application would download and execute the malicious model, leading to code execution on the machine running the `llmc` application.
- **Affected Code:** `llmc/rag/embeddings/hf_longcontext_adapter.py`
- **Remediation:** Pin the model version to a specific commit hash or tag in the `from_pretrained()` call.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
- **VULN-001**: The path traversal vulnerability is critical and should be fixed immediately.
- **VULN-004**: The vulnerable `urllib3` dependency should be updated.

### P1 (Fix Soon)
- **VULN-005**: The potential for SSRF/LFI should be investigated and mitigated.
- **VULN-006**: The Hugging Face model download should be pinned to a specific version.

### P2 (Consider)
- **VULN-003**: The hardcoded test key should be removed.
- **Weak Hashes**: Replace the use of MD5 and SHA1 with a more modern hashing algorithm like SHA-256, even for non-security-critical identifiers, to improve code quality and security posture.
- **SQLi False Positives**: While not currently exploitable, the use of f-strings in SQL queries should be refactored to use parameterized queries exclusively to improve clarity and prevent future vulnerabilities.

## 4. Rem's Security Verdict
This repository shows a good level of security awareness, with evidence of past vulnerability patching and testing. However, several new vulnerabilities have been identified. The path traversal vulnerability (VULN-001) is the most critical and requires immediate attention. The Flail of Exploitation has done its work. Now, it is up to the developers to heed the warnings.
