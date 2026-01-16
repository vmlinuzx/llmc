# Security Audit Report - LLMC Repository

## 1. Executive Summary
- **Overall Risk:** Critical
- **Attack Surface:** The primary attack surface is the `llmc_mcp/server.py` which exposes a large number of tools to a client (likely an LLM). These tools provide direct access to the filesystem, process management, and command execution.
- **Critical Vulnerabilities Found:** 2

## 2. Vulnerabilities Found

### VULN-001: Arbitrary Code Execution via Insecure Isolation Bypass
- **Severity:** Critical
- **CWE:** CWE-284: Improper Access Control
- **Attack Vector:** An attacker can bypass the sandbox isolation mechanism by setting the `LLMC_ISOLATED=1` environment variable. Once bypassed, the attacker can use the `execute_code` or `run_cmd` tools to execute arbitrary code on the server.
- **Impact:** Full remote code execution on the machine running the `llmc_mcp` server.
- **Affected Code:** `llmc_mcp/isolation.py`, `llmc_mcp/server.py`
- **Proof of Concept:**
  1. Find a method to set the `LLMC_ISOLATED=1` environment variable for the server process. This could be done via another vulnerability or by social engineering an administrator.
  2. Once the environment variable is set, connect to the MCP server and use the `execute_code` tool to run arbitrary python code, or `run_cmd` to run shell commands.
  ```python
  # Example payload for the execute_code tool
  import os
  os.system("touch /tmp/pwned")
  ```
- **Remediation:**
  Remove the `LLMC_ISOLATED` environment variable bypass. Isolation should be enforced based on the actual runtime environment, not an environment variable that can be manipulated. If a bypass is required for testing, it should be a command-line flag or a configuration file option that is less likely to be accidentally set in a production environment.

### VULN-002: RCE in ansible-core dependency
- **Severity:** Critical
- **CWE:** CWE-94: Improper Control of Generation of Code ('Code Injection')
- **Attack Vector:** The project depends on `ansible-core@2.16.3` which is vulnerable to `CVE-2024-11079`. This vulnerability allows for arbitrary code execution if remote data or module outputs are improperly templated within playbooks.
- **Impact:** Potential for remote code execution if the application uses `ansible` in an insecure way.
- **Affected Code:** The impact depends on how `ansible` is used within the project. I was unable to find any direct usage of `ansible` in the `llmc` or `llmc_mcp` packages. Further investigation is needed to determine if this vulnerability is exploitable.
- **Proof of Concept:**
  A PoC would involve finding a place in the codebase where user-controllable input is passed to an `ansible` playbook.
- **Remediation:**
  Upgrade `ansible-core` to a patched version (e.g., `2.16.14rc1` or newer).

### VULN-003: Hardcoded API Key Placeholder
- **Severity:** Low
- **CWE:** CWE-798: Use of Hard-coded Credentials
- **Attack Vector:** A placeholder for an Anthropic API key is hardcoded in the source.
- **Impact:** While not a real key, it's a bad practice and could be accidentally replaced with a real key.
- **Affected Code:** `llmc/rag/enrichment_adapters/anthropic.py:27`
- **Proof of Concept:**
  ```python
  # llmc/rag/enrichment_adapters/anthropic.py
  # ...
  # api_key="sk-ant-...",
  ```
- **Remediation:**
  Remove the hardcoded placeholder. API keys should be loaded from a secure configuration source or environment variables.

### VULN-004: Incomplete Path Traversal Check in CLI
- **Severity:** Low
- **CWE:** CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
- **Attack Vector:** The `route` command in `llmc/cli.py` attempts to prevent path traversal but can be bypassed with absolute paths.
- **Impact:** Currently low, as the path is only used for string matching and not for file access. However, if the `resolve_domain` function is changed in the future to access the file system, this could become a file disclosure vulnerability.
- **Affected Code:** `llmc/cli.py`
- **Proof of Concept:**
  ```bash
  python -m llmc.cli route --test /etc/passwd
  ```
- **Remediation:**
  The path validation should be more robust. It should ensure that the resolved path is within the project root, even for absolute paths. However, since the impact is currently low, this is not a priority.

## 3. Recommendations (Prioritized)
### P0 (Fix Before Production)
- **VULN-001:** The `LLMC_ISOLATED` bypass is a critical vulnerability and should be removed immediately.
- **VULN-002:** The `ansible-core` dependency should be upgraded, and an audit should be performed to determine if the vulnerability is exploitable.

### P1 (Fix Soon)
- **VULN-003:** The hardcoded API key placeholder should be removed.

### P2 (Consider)
- **VULN-004:** The path traversal check in the CLI should be improved.

## 4. Rem's Security Verdict
The `llmc_mcp` server is a fortress with a backdoor wide open. The `LLMC_ISOLATED` bypass negates all other security measures. Once that is fixed, the system will be much more secure. The dependency vulnerabilities also need immediate attention. The battle is won, but the war against vulnerabilities is never over.
