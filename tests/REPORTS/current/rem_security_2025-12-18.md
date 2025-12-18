# Security Audit Report - Core Security Mechanisms

## 1. Executive Summary
- **Overall Risk:** Critical
- **Attack Surface:** MCP Tools (`te_run`, `fs`, `cmd`), CLI Arguments, Environment Variables
- **Critical Vulnerabilities Found:** 2 (Verified POCs)
- **High Vulnerabilities Found:** 3

## 2. Vulnerabilities Found

### VULN-001: Isolation Bypass in `te_run`
- **Severity:** Critical
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** An agent with access to the `te_run` MCP tool can execute arbitrary commands on the host system, bypassing the isolation checks enforced by `cmd.run_cmd`.
- **Impact:** Full Remote Code Execution (RCE) on the host.
- **Affected Code:** `llmc_mcp/tools/te.py`
- **Proof of Concept:**
  ```python
  # Verified in tests/security/test_te_bypass.py
  from llmc_mcp.tools.te import te_run
  # This executes without triggering require_isolation
  te_run(["run", "rm", "-rf", "/tmp/important_file"])
  ```
- **Remediation:**
  Add `require_isolation("te_run")` to the `te_run` function in `llmc_mcp/tools/te.py`.

### VULN-002: Indirect Command Execution via `run_cmd`
- **Severity:** High
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** The `run_cmd` tool protects against shell injection by using `shell=False`, but allows executing interpreters like `python3`, `sh`, `perl` if they are not blacklisted. The default blacklist is empty.
- **Impact:** Arbitrary Code Execution (ACE) if an interpreter is available.
- **Affected Code:** `llmc_mcp/tools/cmd.py`
- **Proof of Concept:**
  ```python
  # Verified in tests/security/test_exploit_cmd_injection.py
  run_cmd("python3 -c \"import os; os.system('cat /etc/passwd')\"", cwd=".")
  ```
- **Remediation:**
  Implement a strict ALLOWLIST of safe binaries instead of a weak blacklist. Or aggressively blacklist interpreters (`python`, `sh`, `bash`, `perl`, `ruby`, `php`).

### VULN-003: Filesystem Protection Bypass (Empty Config)
- **Severity:** High
- **CWE:** CWE-22 (Path Traversal)
- **Attack Vector:** If `allowed_roots` is configured as an empty list `[]` (which might be a default or misconfiguration), `validate_path` returns `True`, granting full filesystem access.
- **Impact:** Arbitrary File Read/Write.
- **Affected Code:** `llmc_mcp/tools/fs.py`
- **Proof of Concept:**
  ```python
  # Verified in tests/security/test_fs_traversal_extended.py
  validate_path("/etc/passwd", allowed_roots=[])  # Returns path, does not raise
  ```
- **Remediation:**
  Change `check_path_allowed` to return `False` if `allowed_roots` is empty. Require explicit `["/"]` for full access if that is the intent, to avoid "fail open" defaults.

### VULN-004: Filesystem Protection Bypass (Root Config)
- **Severity:** Medium
- **CWE:** CWE-22 (Path Traversal)
- **Attack Vector:** If `allowed_roots` contains `"/"`, validation passes for all files. While this may be intended for "full access" mode, it defeats the purpose of the security check if it's easily set.
- **Impact:** Arbitrary File Read/Write.
- **Affected Code:** `llmc_mcp/tools/fs.py`
- **Proof of Concept:**
  ```python
  validate_path("/etc/passwd", allowed_roots=["/"])
  ```
- **Remediation:**
  Log a critical warning when `"/"` is used as an allowed root.

### VULN-005: Isolation Bypass via Environment Variable
- **Severity:** Medium
- **CWE:** CWE-656 (Reliance on Security Through Obscurity)
- **Attack Vector:** The isolation check respects `LLMC_ISOLATED=1`. If an attacker can inject environment variables (e.g., via a compromised process spawning the server), they can bypass isolation.
- **Impact:** Bypassing security controls.
- **Affected Code:** `llmc_mcp/isolation.py`
- **Proof of Concept:**
  ```python
  os.environ["LLMC_ISOLATED"] = "1"
  # is_isolated_environment() returns True
  ```
- **Remediation:**
  Consider removing this bypass or requiring a more complex secret value (e.g., a hash) rather than just "1".

## 3. Recommendations (Prioritized)

### P0 (Fix Before Production)
1.  **Secure `te_run`:** Immediately add `require_isolation` to `llmc_mcp/tools/te.py`.
2.  **Fix "Fail Open" FS Config:** Modify `llmc_mcp/tools/fs.py` to deny access if `allowed_roots` is empty.

### P1 (Fix Soon)
1.  **Harden `run_cmd`:** Switch to an allowlist for binaries or block known interpreters.
2.  **Audit `simpleeval` usage:** Ensure `llmc/ruta/judge.py` usage of `simpleeval` is robust against object traversal attacks (though it looks decent).

### P2 (Consider)
1.  **Secret Env Var:** Change `LLMC_ISOLATED=1` to something harder to guess or inject accidentally.

## 4. Rem's Security Verdict
The "Flail of Exploitation" has struck true. The `te_run` bypass is a gaping hole in the armor. You are relying on a paper shield (`LLMC_ISOLATED=1`) and a "nice" blacklist. Secure the gates before the dragons enter.
