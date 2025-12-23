# Security Audit Report - LLMC Repository

## 1. Executive Summary
- **Overall Risk:** High
- **Attack Surface:** The primary attack surface is the `llmc-mcp` server, which exposes a powerful set of tools for filesystem access, command execution, code execution, and database querying. Command-line utilities also present a secondary attack surface.
- **Critical Vulnerabilities Found:** This audit identified several high-risk vulnerabilities, primarily stemming from outdated and vulnerable dependencies. While several critical historical vulnerabilities like command injection and arbitrary code execution have been successfully remediated, the large number of unpatched dependencies in core networking libraries presents a significant risk of compromise.

## 2. Vulnerabilities Found

### VULN-001: Outdated and Vulnerable Dependencies
- **Severity:** High
- **CWE:** CWE-1104: Use of Unmaintained Third Party Components
- **Attack Vector:** Exploitation of known vulnerabilities in third-party packages.
- **Impact:** Varies by dependency, but could range from Denial of Service to Remote Code Execution, especially in web-facing components.
- **Details:** The `pip-audit` scan revealed 25 vulnerabilities in 12 packages. The most critical are:
    - **`tornado` (6.4):** Multiple vulnerabilities (GHSA-753j-mpmx-qq6g, GHSA-w235-7p84-xx57, CVE-2025-47287, CVE-2024-52804). As a core component of the MCP web server, these could lead to serious web-based attacks.
    - **`urllib3` (2.3.0):** Multiple CVEs. Affects all HTTP requests, potentially leading to request smuggling or other parsing-related attacks.
    - **`werkzeug` (3.0.1):** Multiple CVEs. As a WSGI utility library, these vulnerabilities could be exposed through the web server.
    - **`paramiko` (2.12.0):** Vulnerable to the Terrapin attack (CVE-2023-48795), which can downgrade SSH connection security.
- **Remediation:** Update all vulnerable dependencies to the specified fixed versions. Run `pip install -U -r requirements.txt` and verify functionality.

### VULN-002: Potential SQL Injection via F-String Formatting
- **Severity:** High
- **CWE:** CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')
- **Attack Vector:** A malicious user, through a tool like `rag_search`, could provide input that is formatted into an f-string used to construct an SQL query.
- **Impact:** Could allow an attacker to read, modify, or delete data from the RAG database.
- **Affected Code:**
  - `llmc/rag/database.py`
  - `llmc/rag/db_fts.py`
  - `llmc/rag/enrichment_db_helpers.py`
  - `llmc/rag/graph_db.py`
  - `llmc/rag/search/__init__.py`
- **Proof of Concept:**
  ```python
  # Example from llmc/rag/database.py
  # If 'placeholders' is derived from user input, this is vulnerable.
  query = f"DELETE FROM spans WHERE span_hash NOT IN ({placeholders})"
  self.conn.execute(query, list(valid_span_hashes))
  ```
- **Remediation:** Refactor all SQL queries to use parameterized statements exclusively. Never use f-strings or string concatenation to build queries with data that could be influenced by user input.

### VULN-003: Server-Side Request Forgery (SSRF) / Local File Inclusion (LFI)
- **Severity:** Medium
- **CWE:** CWE-918: Server-Side Request Forgery (SSRF)
- **Attack Vector:** An attacker who can control the URL passed to `urllib.request.urlopen` could force the server to make requests to internal services or read local files.
- **Impact:** Information disclosure of internal network services or local files on the server (e.g., via `file:///etc/passwd`).
- **Affected Code:**
  - `llmc/commands/repo_validator.py:376`
  - `llmc/rag/embeddings/check.py:71`
  - `llmc/rag/service_health.py:59`
- **Remediation:** Implement a strict whitelist for all outgoing HTTP requests. Validate that URLs are well-formed and point to expected, trusted domains. Avoid using `urlopen` with user-controllable URLs.

### VULN-004: Supply Chain Risk from Unpinned Hugging Face Downloads
- **Severity:** Medium
- **CWE:** CWE-494: Download of Code Without Integrity Check
- **Attack Vector:** A malicious actor could compromise a Hugging Face model repository and push a malicious update.
- **Impact:** The `llmc` application would download and execute the malicious model code, leading to RCE.
- **Affected Code:** `llmc/rag/embeddings/hf_longcontext_adapter.py:45`
- **Remediation:** Pin all `from_pretrained()` calls to a specific, known-good revision (commit hash).
  ```python
  # Example fix
  self._model = AutoModel.from_pretrained(
      self.model_name,
      revision="<SPECIFIC_COMMIT_HASH>",
      trust_remote_code=self.config.get("trust_remote_code", False),
  )
  ```

### NOTEWORTHY: Remediated Vulnerabilities
It is noted that several critical vulnerabilities appear to have been remediated prior to this audit. This demonstrates positive security momentum.
- **`run_cmd` Command Injection:** The `run_cmd` tool was found to use `shell=True` in the past. It now correctly uses `shell=False` with `shlex.split`, preventing command injection.
- **`execute_code` RCE:** The `execute_code` tool previously used `exec()` in the main process, allowing trivial RCE and DoS. It has been hardened to use a separate `subprocess`, providing process isolation and timeout enforcement.
- **`eval()` Injection:** The `judge` in `llmc/ruta/judge.py` previously used `eval()`, which was replaced by the much safer `simpleeval` library with a function whitelist.
- **Path Traversal:** Filesystem tools in `llmc_mcp/tools/fs.py` show a robust implementation against path traversal, using path canonicalization and root directory validation.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
1.  **Update Dependencies:** Immediately update all vulnerable packages identified by `pip-audit`, especially `tornado`, `urllib3`, and `werkzeug`.
2.  **Fix SQL Injections:** Audit and refactor all SQL queries identified by Bandit to use parameterized statements. This is critical to protect the integrity of the RAG database.

### P1 (Fix Soon)
1.  **Mitigate SSRF/LFI:** Implement whitelisting for all outgoing requests made with `urllib`. Do not trust that input URLs will be safe.
2.  **Pin Hugging Face Models:** Mitigate supply chain risk by pinning all `from_pretrained` calls to specific commit hashes.

### P2 (Consider)
1.  **Replace Weak Hashes:** Replace all usage of `md5` and `sha1` with `sha256`. While not currently used in a security-critical context, it is a bad practice that could lead to vulnerabilities if misused later.

## 4. Rem's Security Verdict
You've patched the gaping wounds I found before, replacing `eval()` and taming `exec()`. Your defenses are more disciplined. But your foundations are rotten. The fortress is built on quicksand—a swamp of outdated dependencies. A single CVE in your networking stack could bring the whole castle down. You've learned to parry a sword, but you ignore the plague creeping through your gates. Patch your dependencies, or I'll be back to dance on the rubble.