# Security Audit Report - LLMC Codebase

## 1. Executive Summary
- **Audit Date:** 2025-12-12
- **Auditor:** Rem the Penetration Testing Demon
- **Overall Risk:** **CRITICAL**
- **Attack Surface:**
    - `llmc_agent`: CLI and RAG integration (Argument Injection)
    - `llmc_mcp`: Code execution and Tooling (DoS, Process Corruption)
- **Critical Vulnerabilities Found:** 3
- **Exploitability:** High (Publicly accessible interfaces, trivial exploits)

## 2. Threat Model
- **Assets:** User's local filesystem, LLMC configuration, MCP server process availability.
- **Adversaries:** Malicious actors controlling:
    - RAG queries (via prompt injection or direct input).
    - Code execution payloads (via MCP).
- **Trust Boundaries:**
    - `LLMCBackend.search(query)`: Untrusted string -> Shell Command.
    - `execute_code(code)`: Untrusted code -> Python `exec()`.

## 3. Vulnerabilities Found

### VULN-001: Argument Injection in RAG Backend
- **Severity:** High
- **CWE:** CWE-88: Improper Neutralization of Argument Delimiters in a Command ('Argument Injection')
- **Attack Vector:**
    - An attacker supplies a search query starting with `-` (e.g., `--help`, `--version`, or worse).
    - The `llmc_agent/backends/llmc.py` script passes this query directly to `rg` or `llmc-cli` without the `--` delimiter.
- **Impact:**
    - Modification of search tool behavior.
    - Potential DoS (huge searches).
    - Information Disclosure (if flags allow outputting other files).
- **Affected Code:**
    - `llmc_agent/backends/llmc.py:86` (`subprocess.run(["rg", ... query])`)
    - `llmc_agent/backends/llmc.py:126` (`subprocess.run(["llmc-cli", ... query])`)
- **Remediation:**
    - Insert `--` before the query argument in all `subprocess.run` calls.
    ```python
    subprocess.run(["rg", ..., "--", query], ...)
    ```

### VULN-002: Denial of Service in Code Execution
- **Severity:** High
- **CWE:** CWE-400: Uncontrolled Resource Consumption
- **Attack Vector:**
    - An attacker submits Python code with an infinite loop (`while True: pass`).
    - The `execute_code` function uses `exec()` which blocks the main thread.
    - The provided `timeout` parameter catches `subprocess.TimeoutExpired` but `exec()` is not a subprocess.
- **Impact:**
    - The MCP server hangs indefinitely.
    - Requires manual restart of the service.
- **Affected Code:**
    - `llmc_mcp/tools/code_exec.py:291` (`exec(compiled, namespace)`)
- **Remediation:**
    - Run code execution in a separate process (e.g., `multiprocessing.Process` or `subprocess`).
    - Enforce timeouts on the external process.

### VULN-003: Process State Corruption
- **Severity:** High
- **CWE:** CWE-1105: Insufficient Isolation of Shared Resources
- **Attack Vector:**
    - `execute_code` runs in the same process/interpreter as the MCP server.
    - Attacker code can modify `os.environ`, `sys.modules`, or built-ins.
- **Impact:**
    - Leakage of environment variables.
    - Destabilization of the MCP server.
    - Potential privilege escalation if the server has secrets in memory.
- **Affected Code:**
    - `llmc_mcp/tools/code_exec.py`
- **Remediation:**
    - Use strict process isolation (Docker, nsjail) for *every* execution, not just checking if the *server* is in a container.
    - At minimum, run user code in a separate subprocess to protect the server's memory space.

## 4. Security Strengths
- **Isolation Checks:** `llmc_mcp.isolation` correctly identifies containerized environments.
- **Safe Eval:** `llmc/ruta/judge.py` uses `simpleeval`, preventing the previous RCE vulnerability.
- **Command Security:** `llmc_mcp/tools/cmd.py` uses `shell=False` and `shlex.split`.

## 5. Recommendations
### P0 (Immediate Fix)
1.  **Fix Argument Injection:** Update `llmc_agent/backends/llmc.py` to use `--` delimiter.
2.  **Fix Code Exec DoS:** Refactor `execute_code` to spawn a subprocess (even just `python -c ...`) so timeouts work and process state is isolated.

### P1 (Soon)
1.  **Enforce Sandbox:** Make `require_isolation` check for a specific *sandbox* (like nsjail) rather than just "is docker". Docker containers are not security boundaries for root users.

## 6. Rem's Vicious Security Verdict
You've patched the obvious holes (`eval`, `shell=True`), but you left the door wide open with `exec()` in the main thread. A script kiddy could hang your entire server with `while True: pass`. And passing user input to `rg` without `--`? Amateur hour. Fix it before I replace your `rg` with `rm`.
