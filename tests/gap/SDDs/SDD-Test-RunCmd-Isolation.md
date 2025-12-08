# SDD: Add `run_cmd` Isolation Tests

## 1. Gap Description
`run_cmd` enforces execution in an isolated environment using `require_isolation`. While the code exists, there are no tests verifying that:
1.  `run_cmd` fails when *not* isolated.
2.  `run_cmd` passes when `LLMC_ISOLATED=1` is set.
3.  `run_cmd` passes when container markers are present (mocked).

## 2. Target Location
- Test: `tests/mcp/test_cmd_isolation.py`

## 3. Test Strategy
1.  **Mock Environment**: Use `unittest.mock.patch.dict` to manipulate `os.environ`.
2.  **Mock Filesystem**: Mock `pathlib.Path.exists` to simulate `/.dockerenv` etc.
3.  **Test Cases**:
    -   **No Isolation**: Clear all markers. Call `run_cmd`. Assert failure (ExecResult with error).
    -   **Env Var**: Set `LLMC_ISOLATED=1`. Call `run_cmd`. Assert success (or at least valid execution attempt).
    -   **Docker**: Mock `/.dockerenv`. Call `run_cmd`. Assert success.

## 4. Implementation Details
-   Import `run_cmd` from `llmc_mcp.tools.cmd`.
-   Focus on the *security check*, not the actual command execution (mock `subprocess.run` to avoid side effects).
