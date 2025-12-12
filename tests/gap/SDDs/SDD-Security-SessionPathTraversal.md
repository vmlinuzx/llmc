# SDD: Path Traversal in Session Manager

## 1. Gap Description
The `llmc_agent/session.py` file allows `session_id` to be used directly in file path construction: `path = self.sessions_dir / f"{session_id}.json"`. This allows path traversal characters (`../`) to escape the sessions directory.

While exploitability is limited by the `.json` extension and schema validation on load, it is a security best practice violation. A user could potentially overwrite a valid session file in another directory if they can guess its path and name (e.g., `../../other_project/.llmc/sessions/target_id`).

## 2. Target Location
`tests/gap/security/test_session_path_traversal.py`

## 3. Test Strategy
1.  **Setup**: Create a `SessionManager` with a temporary directory.
2.  **Scenario**: Attempt to `load` a session with ID `../traversal`.
3.  **Assertion**: The path resolved should be outside the `sessions` subdirectory.
    *   Ideally, the code should raise a `ValueError` or return `None` *before* hitting the filesystem, or `path.resolve()` should check for parent directory escape.
    *   Since we are reproducing the gap, we verify that it *does* try to access the escaped path.
    *   We can create a dummy JSON file at the escaped location (valid session format) and verify it loads.

## 4. Implementation Details
*   Create a temporary directory structure: `root/sessions` and `root/outside.json`.
*   Write valid session JSON to `root/outside.json`.
*   Initialize `SessionManager` at `root`.
*   Call `load("../outside")`.
*   Assert that the returned session matches the content of `outside.json`.
