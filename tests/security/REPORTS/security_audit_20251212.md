# Security Audit Report - LLMC Core & Agent

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** Agent Tool System, MCP Server, RAG Backend
- **Critical Vulnerabilities Found:** 3
- **Exploitability:** High (trivial exploitation of tool tiering and argument injection)

## 2. Threat Model
- **Assets:** User filesystem, sensitive files (SSH keys, credentials), system integrity.
- **Adversaries:** Malicious prompts (Prompt Injection), untrusted tool execution environment.
- **Attack Vectors:**
    1.  **Prompt Injection:** Tricking the agent into unlocking write tools.
    2.  **Argument Injection:** Injecting flags into `rg` or `llmc-cli` commands.
    3.  **Misconfiguration:** Default `allowed_roots=[]` grants full filesystem access.

## 3. Vulnerabilities Found

### VULN-001: Trivial Tool Tier Escalation (Privilege Escalation)
- **Severity:** **CRITICAL**
- **CWE:** CWE-269 (Improper Privilege Management)
- **Attack Vector:** Prompt Injection
- **Impact:** An attacker can unlock "write" capabilities (Tier 2/RUN) simply by including words like "fix" or "edit" in the prompt.
- **Affected Code:** `llmc_agent/tools.py:detect_intent_tier`
- **Proof of Concept:**
  ```python
  # Logic check
  tier = detect_intent_tier("I found a bug, please fix it.")
  assert tier == ToolTier.RUN  # Granting write access based on a word!
  ```
- **Remediation:** Remove auto-tiering based on keywords. Tool capabilities should be explicitly granted by the user at startup (e.g., `--allow-write`) or require explicit confirmation for *every* write operation (which is partially implemented but bypassed by the tier logic being the gatekeeper).

### VULN-002: Insecure Default Sandboxing (Broken Access Control)
- **Severity:** **HIGH**
- **CWE:** CWE-284 (Improper Access Control)
- **Attack Vector:** Misconfiguration
- **Impact:** If `allowed_roots` is empty (default in some contexts), the system grants FULL filesystem access.
- **Affected Code:** `llmc_mcp/tools/fs.py:check_path_allowed`
- **Proof of Concept:**
  ```python
  # Empty list grants full access
  assert check_path_allowed(Path("/etc/passwd"), []) is True
  ```
- **Remediation:** Change the default to **deny all**. If `allowed_roots` is empty, no access should be allowed, or it should default to the current working directory ONLY.

### VULN-003: Argument Injection in RAG Search (Command Injection)
- **Severity:** **MEDIUM**
- **CWE:** CWE-88 (Argument Injection)
- **Attack Vector:** Malicious Query
- **Impact:** A user query starting with `-` is interpreted as a flag by `rg` or `llmc-cli`. While `subprocess` prevents shell injection, flag injection can cause denial of service or unexpected behavior (e.g., passing `--help` or other control flags).
- **Affected Code:** `llmc_agent/backends/llmc.py`
- **Proof of Concept:**
  ```python
  # Backend executes: ["llmc-cli", "analytics", "search", "--help"]
  # Instead of: ["llmc-cli", "analytics", "search", "--", "--help"]
  ```
- **Remediation:** Insert the `--` delimiter before user-controlled arguments in all `subprocess.run` calls.

## 4. Security Strengths
- **Path Canonicalization:** `llmc_mcp/tools/fs.py` correctly uses `pathlib.Path.resolve()` to defeat path traversal and symlink attacks.
- **Subprocess Usage:** Widespread use of `subprocess.run(shell=False)` prevents classic shell command injection (`; rm -rf /`).

## 5. Recommendations (Prioritized)

### P0 (Fix Immediately)
1.  **Fix VULN-003:** Patch `llmc_agent/backends/llmc.py` to add `--` delimiter.
2.  **Fix VULN-002:** Change `check_path_allowed` to return `False` if `allowed_roots` is empty, or enforce a strict default in `ToolRegistry`.
3.  **Fix VULN-001:** Disable `detect_intent_tier` auto-escalation. Default to Read-Only. Require explicit user flag for Write access.

### P1 (Hardening)
1.  **Audit `run_cmd` Blacklist:** The default blacklist is empty. Implement a "White-list" approach for allowed binaries instead of a Blacklist.
2.  **Secrets Management:** Ensure no secrets are logged in debug mode.

## 9. Rem's Vicious Security Verdict
You built a fortress with a secure door (`resolve()`), but you left the key under the mat (`detect_intent_tier`) and unlocked the back door by default (`allowed_roots=[]`).
The argument injection is sloppy.
**Fix these or be pwned.**
