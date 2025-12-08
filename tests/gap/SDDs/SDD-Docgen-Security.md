# SDD: DocgenCoordinator Arbitrary File Read Vulnerability

## 1. Gap Description
The `DocgenCoordinator` class in `llmc_mcp/docgen_guard.py` lacks validation to ensure `source_path` is within the repository.
- `compute_source_hash` reads the file content to compute SHA256.
- `docgen_file` calls `compute_source_hash` before any path validation.

This allows an attacker (or buggy agent) to read/hash arbitrary files on the filesystem (e.g., `/etc/passwd`, `~/.ssh/id_rsa`) if the process has permissions.

## 2. Target Location
`tests/gap/test_docgen_security.py`

## 3. Test Strategy
We will create a test that attempts to invoke `docgen_file` on a sensitive system file (or a temp file outside the "repo").

**Scenario: Out-of-bounds Read**
1.  Create a temporary file *outside* the simulated repo root.
2.  Initialize `DocgenCoordinator` with a fake repo root.
3.  Call `docgen_file` with the outside file path.
4.  **Expectation (Current Behavior)**: The call succeeds (returns a result or throws no security error), verifying the vulnerability.
5.  **Goal**: The test should FAIL if the vulnerability exists (or PASS if we assert that it *should* raise a security error).
    *   Since I am *finding* gaps, I will write a test that expects a `ValueError` or `SecurityError` when accessing outside files. If the code is vulnerable, this test will fail (which is good, it exposes the gap).

## 4. Implementation Details
- Use `tempfile` to create a "repo" dir and a "secret" file outside it.
- Initialize `DocgenCoordinator`.
- Assert that calling `docgen_file(secret_file)` raises `ValueError` or `PermissionError`.
- Also assert that `compute_source_hash` raises if called directly with outside file (if we want to lock it down there).

**Note**: The test will likely fail (Red) because the code currently allows it. This confirms the gap.
