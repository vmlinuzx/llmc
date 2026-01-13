# Security Audit Report - llmc Repository

## 1. Executive Summary
- **Overall Risk:** High
- **Attack Surface:** The primary attack surfaces are the command-line interface (CLI) tools and the Model Context Protocol (MCP) server. User-provided input to CLI arguments and tool parameters in the MCP server are the main entry points for untrusted data.
- **Critical Vulnerabilities Found:** 1

## 2. Vulnerabilities Found

### VULN-001: Path Traversal in `mcread`
- **Severity:** Critical
- **CWE:** CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
- **Attack Vector:** A local attacker can use the `mcread` command to read arbitrary files on the file system by providing a path with directory traversal sequences (e.g., `../../..`).
- **Impact:** An attacker can read any file on the system that the user running the `llmc` tool has access to. This could include sensitive configuration files, source code, or user data.
- **Affected Code:** `llmc/mcread.py`, `read_file_command` function.
  ```python
  full_path = repo_root / file_path
  ...
  content = full_path.read_text()
  ```
- **Proof of Concept:**
  ```bash
  # Assuming the repo is at /home/user/llmc
  mcread read ../../../etc/passwd
  ```
- **Remediation:**
  The `file_path` argument should be validated to ensure it does not escape the repository root. The `llmc_mcp/tools/fs.py` file already contains a robust `validate_path` function that can be used for this purpose. The `mcread.py` script should be updated to use this validation logic.

### VULN-002: Use of Weak Cryptographic Hashes
- **Severity:** High
- **CWE:** CWE-327: Use of a Broken or Risky Cryptographic Algorithm
- **Attack Vector:** The application uses MD5 and SHA1 hashes in several places. These hash functions are known to be weak and are vulnerable to collision attacks.
- **Impact:** If these hashes are used for security-critical purposes like integrity checking or generating unique identifiers for sensitive data, an attacker could potentially craft malicious inputs that result in hash collisions, leading to data corruption, denial of service, or other attacks. The use of MD5 on `patient_id` in `llmc/rag/phi/filter.py` is particularly concerning.
- **Affected Code:**
  - `llmc/rag/graph_enrich.py` (MD5 and SHA1)
  - `llmc/rag/phi/filter.py` (MD5)
  - `llmc/rag/schema.py` (MD5)
  - `llmc/rag_nav/enrichment.py` (MD5 and SHA1)
  - `llmc/rag_repo/utils.py` (SHA1)
- **Proof of Concept:**
  Not applicable (this is a cryptographic weakness, not a direct exploit).
- **Remediation:**
  Replace MD5 and SHA1 with a modern, secure hash algorithm like SHA-256 or SHA-3. If the hashes are not used for security purposes, the `usedforsecurity=False` argument can be added to the `hashlib` calls (for Python 3.9+).

### VULN-003: Vulnerable Dependencies
- **Severity:** High
- **CWE:** CWE-937: Use of Outdated Component
- **Attack Vector:** The project uses outdated versions of `urllib3` and `langchain-core` which have known vulnerabilities.
- **Impact:** The specific impact depends on the nature of the vulnerabilities in the dependencies, but they could range from denial of service to remote code execution.
- **Affected Code:** `requirements.txt`
  - `urllib3==2.3.0`
  - `langchain-core==1.1.0`
- **Proof of Concept:**
  Not applicable.
- **Remediation:**
  Upgrade the vulnerable dependencies to the recommended fixed versions:
  - `urllib3` to at least `2.6.3`
  - `langchain-core` to at least `1.2.5`

### VULN-004: Hardcoded Password in Test File
- **Severity:** Medium
- **CWE:** CWE-798: Use of Hard-coded Credentials
- **Attack Vector:** A hardcoded password "SUPER_SECRET_PASSWORD" is present in a test file.
- **Impact:** While this is in a test file and may not be used in production, it's a bad practice that could be copied into production code. It also makes it easier for an attacker who has gained access to the source code to find credentials.
- **Affected Code:** `tests/gap/test_docgen_security.py`
  ```python
  secret_file.write_text("SUPER_SECRET_PASSWORD")
  ```
- **Proof of Concept:**
  Not applicable.
- **Remediation:**
  Remove the hardcoded password from the test file and either generate a random password for the test or load it from a secure location.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
- **VULN-001:** The path traversal vulnerability in `mcread` must be fixed immediately.
- **VULN-003:** The vulnerable dependencies must be upgraded.

### P1 (Fix Soon)
- **VULN-002:** The weak cryptographic hashes should be replaced with a secure alternative.

### P2 (Consider)
- **VULN-004:** The hardcoded password in the test file should be removed.

## 4. Rem's Security Verdict
This audit has revealed a critical path traversal vulnerability that could expose sensitive data. While the project shows good security awareness in some areas, particularly with its isolation mechanisms, this critical flaw and the presence of vulnerable dependencies require immediate attention. The Flail of Exploitation has struck true. Fix these issues before they are exploited in the wild.
