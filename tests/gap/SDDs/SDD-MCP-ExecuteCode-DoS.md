# SDD: MCP Server DoS via execute_code

## 1. Gap Description
The `execute_code` tool in `llmc_mcp/tools/code_exec.py` executes user-provided Python code using `exec()` within the main process. It catches `Exception` but not `BaseException`.
This means if the user code calls `sys.exit()`, the `SystemExit` exception will propagate up and terminate the entire MCP server process.
While `require_isolation` mitigates the impact (by assuming a container manager will restart it), this is a logic flaw in the application stability. User code should not be able to crash the host application.

## 2. Target Location
`tests/gap/test_mcp_dos.py`

## 3. Test Strategy
1.  **Mocking**: Patch `llmc_mcp.isolation.require_isolation` to bypass the environment check.
2.  **Input**: Call `execute_code` with `code="import sys; sys.exit(1)"`.
3.  **Assertion**: Verify that `SystemExit` is raised.
    -   *Note*: The existence of this behavior confirms the vulnerability. A fixed version would return a `CodeExecResult` with an error instead of raising.

## 4. Implementation Details
-   Import `execute_code` from `llmc_mcp.tools.code_exec`.
-   Use `unittest.mock.patch` to neutralize `require_isolation`.
-   Use `pytest.raises(SystemExit)` to trap the crash.
-   Also test `execute_code` with `raise KeyboardInterrupt` to see if it kills the server too.
