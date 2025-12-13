# Security Audit Report - LLMC Core & MCP

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Tools (`execute_code`, `run_cmd`), RUTA Judge, CLI Passthrough
- **Critical Vulnerabilities Found:** 3
- **Exploitability:** 5/5 (Trivial)

The audit revealed catastrophic security failures in the MCP tool implementations. The `execute_code` tool runs arbitrary Python code **in-process**, allowing immediate theft of API keys and Denial of Service. The `run_cmd` tool allows arbitrary shell command execution with an empty blacklist, relying on a "sandbox" check that can be trivially bypassed via environment variables.

## 2. Threat Model
- **Assets:** API Keys (Anthropic, OpenAI), Host Filesystem, MCP Server Availability.
- **Adversaries:** Malicious Agents, Compromised Users, RUTA Scenario Authors.
- **Attack Vectors:**
    1.  **Code Execution:** Submitting Python code to `execute_code`.
    2.  **Command Injection:** Submitting shell commands to `run_cmd`.
    3.  **Eval Injection:** Malformed RUTA properties (mitigated but risk remains).

## 3. Vulnerabilities Found

### VULN-001: Critical Information Disclosure via `execute_code`
- **Severity:** **CRITICAL**
- **CWE:** CWE-200 (Exposure of Sensitive Information)
- **Attack Vector:** Call `execute_code` with `import os; print(os.environ)`
- **Impact:** Attacker steals `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and other secrets from the MCP server process memory.
- **Affected Code:** `llmc_mcp/tools/code_exec.py:execute_code` (uses `exec()` in main process).
- **Proof of Concept:** `tests/security/test_code_exec_breakout.py::test_code_exec_exfiltrates_env_vars`

### VULN-002: Denial of Service via In-Process Execution
- **Severity:** **CRITICAL**
- **CWE:** CWE-400 (Uncontrolled Resource Consumption)
- **Attack Vector:** Call `execute_code` with `while True: pass` or `time.sleep(999)`
- **Impact:** The MCP server hangs indefinitely. The `timeout` parameter is ignored because `exec()` blocks the main thread/process.
- **Affected Code:** `llmc_mcp/tools/code_exec.py`

### VULN-003: Arbitrary Command Execution via Empty Blacklist
- **Severity:** **CRITICAL**
- **CWE:** CWE-78 (OS Command Injection)
- **Attack Vector:** Bypass isolation check (set `LLMC_ISOLATED=1`), then call `run_cmd("rm -rf /")`.
- **Impact:** Full compromise of the host system. The `DEFAULT_BLACKLIST` is empty, blocking nothing.
- **Affected Code:** `llmc_mcp/tools/cmd.py`

### VULN-004: Weak Isolation Enforcement
- **Severity:** **HIGH**
- **CWE:** CWE-653 (Improper Isolation)
- **Attack Vector:** Set `LLMC_ISOLATED=1` env var.
- **Impact:** Disables all security warnings for dangerous tools without actually providing isolation.
- **Affected Code:** `llmc_mcp/isolation.py`

### VULN-005: Type Confusion in RUTA Judge
- **Severity:** **MEDIUM**
- **CWE:** CWE-843 (Access of Resource Using Incompatible Type)
- **Attack Vector:** RUTA property accessing attributes of objects in context.
- **Impact:** Potential information disclosure if sensitive objects are passed to validation context.
- **Affected Code:** `llmc/ruta/judge.py` (`simpleeval` configuration)

## 4. Security Strengths
- **RUTA Eval Patch:** The previous `eval()` vulnerability in RUTA was correctly patched with `simpleeval`, blocking direct `__import__` and `open()` calls.
- **TE CLI:** The `te` tool uses `subprocess.run(shell=False)` correctly, preventing standard shell injection attacks (though it allows all commands by design).

## 5. Recommendations (Prioritized)

### P0 (Fix Immediately)
1.  **Sandboxed Execution:** Rewrite `execute_code` to spawn a **subprocess** (at minimum) or a Docker container. **NEVER** use `exec()` in the main process.
2.  **Isolation Enforcement:** Remove the `LLMC_ISOLATED=1` bypass or restrict it to authenticated debug modes only. Modify `require_isolation` to actually *verify* capability restrictions (e.g., check `unshare` or restricted capabilities), not just file markers.
3.  **Populate Blacklist:** Add dangerous binaries to `llmc_mcp/tools/cmd.py` blacklist: `rm`, `dd`, `mkfs`, `chmod`, `chown`, `wget`, `curl`, `nc`, `bash`, `sh`, `python`.

### P1 (Fix Soon)
1.  **Harden simpleeval:** Disable attribute access in `simpleeval` or wrap context objects in safe proxies.
2.  **Input Sanitization:** Sanitize `te` CLI inputs before logging to SQL to prevent potential SQL injection in telemetry (though not confirmed in this pass).

## 6. Rem's Vicious Security Verdict
I asked for a challenge, and you gave me a sieve. `exec()` in the main process? Storing API keys in the same env you let the AI read? This isn't "Code Mode", it's "Suicide Mode". I didn't even need the Flail of Exploitation; a stern look caused your security posture to collapse. Fix it, or I'm taking the server.

**Score:** 0/10 (Critical Fail)
