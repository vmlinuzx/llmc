# Security Audit Report - LLMC Codebase

## 1. Executive Summary
- **Overall Risk:** **CRITICAL**
- **Attack Surface:** MCP Server (`execute_code`), CLI arguments, File System.
- **Critical Vulnerabilities Found:** 1 (plus 1 previously reported/remediated issue verified).
- **Exploitability:** 5/5 (Trivial RCE in "Code Mode")

## 2. Threat Model
- **Assets:** Host environment variables (API keys), Source code, System availability.
- **Adversaries:** Malicious MCP client, Compromised Agent, User running untrusted RAG/TE commands.
- **Attack Vectors:**
    1.  **Code Execution:** Submitting Python code to `execute_code` tool.
    2.  **DoS:** Submitting infinite loops/blocking code to `execute_code`.

## 3. Vulnerabilities Found

### VULN-001: Arbitrary Code Execution & Data Exfiltration in MCP Server
- **Severity:** **CRITICAL**
- **CWE:** CWE-94 (Improper Control of Generation of Code)
- **Attack Vector:** The `execute_code` tool in `llmc_mcp/tools/code_exec.py` executes user-provided Python code using `exec()` within the main server process.
- **Impact:** 
    - **Data Exfiltration:** Malicious code can read `os.environ` to steal `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and other secrets.
    - **Denial of Service:** Code runs in the main thread. A simple `time.sleep(100)` or `while True: pass` freezes the entire MCP server, causing all other requests to timeout/fail.
    - **Process Compromise:** The attacker can modify the server's memory state, monkey-patch functions, or crash the process.
- **Affected Code:** `llmc_mcp/tools/code_exec.py`
- **Proof of Concept:**
  ```python
  # See tests/security/test_code_exec_breakout.py
  execute_code(code="import os; _result_ = os.environ", ...)
  ```
- **Remediation:**
  1.  **Immediate:** Disable `execute_code` or enforce `LLMC_ISOLATED=1` checking strictly (though checking is easily bypassed if the server is not actually isolated).
  2.  **Structural:** Move code execution to a separate **subprocess** or **container**. Never use `exec()` in the main process.
  ```python
  # Better approach (Subprocess)
  subprocess.run([sys.executable, "-c", code], timeout=timeout, ...)
  ```

## 4. Security Strengths
- **Path Traversal:** `llmc_mcp/tools/fs.py` implements robust checks (`normalize_path`, `check_path_allowed`, `_check_symlink_escape`). Tests confirm `..` and absolute paths are blocked.
- **Shell Injection:** `llmc/te/cli.py` and `llmc_mcp/tools/cmd.py` correctly use `subprocess.run(..., shell=False)` with argument lists.
- **Expression Evaluation:** `llmc/ruta/judge.py` uses `simpleeval` with a strict whitelist, mitigating previous `eval()` risks.

## 5. Missing Security Controls
- **Process Isolation:** The "Code Mode" feature relies on the host being disposable (container) rather than the application being secure.
- **Secrets Management:** Secrets are passed via environment variables which are accessible to the vulnerable `exec()` context.

## 6. Recommendations (Prioritized)

### P0 (Critical - Fix Immediately)
1.  **Refactor `execute_code`:** Stop using `exec()` in the main process. Spawn a subprocess (e.g., `python -c ...`) to execute user code. This provides process isolation (memory protection) and allows proper timeout handling (via `subprocess.TimeoutExpired`).

### P1 (High)
1.  **Secrets Isolation:** If code execution remains, ensure the execution environment does *not* inherit the parent process's environment variables (specifically API keys). Pass only necessary variables.

### P2 (Medium)
1.  **Dependency Scanning:** Integrate `pip-audit` into the CI/CD pipeline to catch vulnerable dependencies automatically.

## 7. Security Test Coverage
- **Tested:**
    - `execute_code` (Exfiltration, DoS) - **VULNERABLE**
    - `read_file` (Path Traversal) - **SAFE**
    - `te` CLI (Shell Injection) - **SAFE**
    - `ruta` Judge (Eval Injection) - **SAFE**
- **Not Tested:**
    - Network-based attacks against the MCP HTTP server (DDos, Header poisoning).
    - Database injection (SQLite FTS5 usage seems safe via parameterized queries, but deep audit wasn't performed).

## 8. Rem's Vicious Security Verdict
**"You built a castle with solid walls (`fs.py`), a sturdy gate (`cmd.py`), and then you invited the Trojan Horse right into the throne room (`execute_code`). Using `exec()` in your main process is suicidal. I didn't even need to hack you; I just asked nicely for your keys, and you handed them over. Fix this before I replace your entire codebase with a single `rm -rf` script."**
