# Security Audit Report - Isolation & Command Execution

## 1. Executive Summary
- **Overall Risk:** Critical
- **Attack Surface:** The `llmc` CLI (specifically `te`) and `llmc_mcp` isolation mechanisms.
- **Critical Vulnerabilities Found:** 3

## 2. Vulnerabilities Found

### VULN-001: Isolation Mechanism Bypass via Environment Variable
- **Severity:** High
- **CWE:** CWE-78: Improper Neutralization of Special Elements used in an OS Command
- **Attack Vector:** An attacker who can inject environment variables (e.g., via a tool that allows setting env vars) can set `LLMC_ISOLATED=1` to bypass the `is_isolated_environment()` check.
- **Impact:** This allows execution of dangerous tools (like `run_cmd`) on a non-isolated host, potentially leading to host compromise.
- **Affected Code:** `llmc_mcp/isolation.py:27`
- **Proof of Concept:**
  See `tests/security/test_isolation_bypass_poc.py`.
  ```python
  with patch.dict(os.environ, {"LLMC_ISOLATED": "1"}):
      assert is_isolated_environment() is True
      # run_cmd works on host
  ```
- **Remediation:**
  Remove the environment variable bypass or secure it with a secret token/authentication.

### VULN-002: `te run` Command Bypasses Isolation Checks
- **Severity:** High
- **CWE:** CWE-250: Execution with Unnecessary Privileges
- **Attack Vector:** The `te run` command executes arbitrary commands using `subprocess.run` without verifying if the environment is isolated.
- **Impact:** If `te` is enabled (it is disabled by default, but intended for use), it allows executing commands on the host without the protections enforced by `run_cmd` (which calls `require_isolation`).
- **Affected Code:** `llmc/te/cli.py` (`_handle_passthrough` function)
- **Proof of Concept:**
  See `tests/security/test_isolation_bypass_poc.py`.
  `te run echo "pwned"` executes directly on host.
- **Remediation:**
  Add `require_isolation("te")` call in `llmc/te/cli.py` before executing commands, or restrict `te` to only safe operations.

### VULN-003: Dangerous Default Configuration for `run_cmd`
- **Severity:** Medium
- **CWE:** CWE-276: Incorrect Default Permissions
- **Attack Vector:** The `llmc.toml` configuration enables `run_cmd` by default.
- **Impact:** Increases the attack surface significantly out-of-the-box. `run_cmd` allows arbitrary command execution (empty blacklist).
- **Affected Code:** `llmc.toml`
- **Proof of Concept:**
  ```toml
  [mcp.tools]
  enable_run_cmd = true
  ```
- **Remediation:**
  Change default to `enable_run_cmd = false`.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
- **VULN-002:** Fix `te run` to enforce isolation. Even if disabled by default, code that bypasses security controls is dangerous.
- **VULN-001:** Remove the debug bypass or secure it.

### P1 (Fix Soon)
- **VULN-003:** Disable `run_cmd` by default in shipped configuration.

## 4. Rem's Security Verdict
The isolation mechanism is Swiss cheese. I walked right through the front door with an environment variable, and the `te` CLI didn't even check the door. If `te` gets enabled, it's game over.
