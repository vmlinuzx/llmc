# AAR: Security Gap Analysis - Command Execution & Injection

## 1. Executive Summary
An autonomous gap analysis was performed on the `llmc`, `llmc_agent`, and `llmc_mcp` codebases. Three security gaps were identified, documented, and reproduced with failing tests.

1.  **Argument Injection in RAG Backend**: The agent backend invokes `rg` and `llmc-cli` without argument delimiters, allowing users to inject flags via search queries.
2.  **Command Allowlist Bypass**: The MCP server configuration defines an `allowlist` for command execution, but the configuration loader ignores it, falling back to an empty `blacklist` which allows all commands.
3.  **Session Path Traversal**: The session manager uses unvalidated session IDs in file paths, allowing traversal outside the sessions directory.

## 2. Gaps Identified

### Gap 1: Argument Injection in RAG Backend
*   **Severity**: High
*   **Location**: `llmc_agent/backends/llmc.py`
*   **Description**: `subprocess.run` is called with user input as a positional argument without a preceding `--` delimiter.
*   **SDD**: `tests/gap/SDDs/SDD-Security-RAGArgInjection.md`
*   **Reproduction Test**: `tests/gap/security/test_rag_arg_injection.py`
*   **Status**: REPRODUCED (Test Failing)

### Gap 2: Command Allowlist Configuration Mismatch
*   **Severity**: Critical
*   **Location**: `llmc_mcp/config.py` / `llmc.toml`
*   **Description**: `llmc.toml` uses `run_cmd_allowlist`, but `config.py` reads `run_cmd_blacklist`. The mismatch results in an empty blacklist, effectively allowing all commands.
*   **SDD**: `tests/gap/SDDs/SDD-Security-CmdAllowlist.md`
*   **Reproduction Test**: `tests/gap/security/test_cmd_allowlist_config.py`
*   **Status**: REPRODUCED (Test Failing)

### Gap 3: Session Path Traversal
*   **Severity**: Medium
*   **Location**: `llmc_agent/session.py`
*   **Description**: `SessionManager.load` and `save` allow session IDs with directory traversal characters (e.g. `../`), enabling access to files outside the intended directory.
*   **SDD**: `tests/gap/SDDs/SDD-Security-SessionPathTraversal.md`
*   **Reproduction Test**: `tests/gap/security/test_session_path_traversal.py`
*   **Status**: REPRODUCED (Test Passing - proving traversal works)

## 3. Recommendations
1.  **Fix Gap 1**: Update `llmc_agent/backends/llmc.py` to insert `"--"` before the `query` argument in all `subprocess.run` calls involving `rg` or `llmc-cli`.
2.  **Fix Gap 2**: Update `llmc_mcp/config.py` to read `run_cmd_allowlist` from the TOML configuration and map it correctly to `McpToolsConfig`. Update `llmc_mcp/tools/cmd.py` to support Allowlist logic.
3.  **Fix Gap 3**: Update `llmc_agent/session.py` to validate `session_id` using a regex (e.g., `^[a-zA-Z0-9_-]+$`) or checking `os.path.commonpath`.

## 4. Artifacts
*   `tests/gap/SDDs/SDD-Security-RAGArgInjection.md`
*   `tests/gap/SDDs/SDD-Security-CmdAllowlist.md`
*   `tests/gap/SDDs/SDD-Security-SessionPathTraversal.md`
*   `tests/gap/security/test_rag_arg_injection.py`
*   `tests/gap/security/test_cmd_allowlist_config.py`
*   `tests/gap/security/test_session_path_traversal.py`
