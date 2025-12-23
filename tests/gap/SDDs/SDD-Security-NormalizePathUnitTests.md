# SDD: Core Security - normalize_path Unit Tests

## 1. Gap Description

The core security function `llmc.security.normalize_path` lacks a dedicated suite of security unit tests. Existing path traversal tests in `tests/security/test_path_traversal.py` target a different, higher-level function (`validate_source_path`).

This leaves the foundational security primitive without direct, explicit validation against critical attack vectors. We must test this function directly to ensure its integrity, as it may be used in contexts not covered by the existing high-level tests.

## 2. Target Location

A **new test file** shall be created at: `tests/security/test_security_normalize_path.py`

## 3. Test Strategy

The tests will directly import and call `llmc.security.normalize_path`. Each test will construct a scenario representing a specific attack vector and assert that the function correctly raises a `PathSecurityError`. The tests will use a temporary directory structure to simulate a secure `repo_root`.

## 4. Implementation Details

The new test file must include the following test cases:

1.  **`test_normalize_path_basic_traversal`**:
    -   Pass various `../` style paths (e.g., `../../etc/passwd`).
    -   Assert that `PathSecurityError` is raised.

2.  **`test_normalize_path_absolute_path_traversal`**:
    -   Pass an absolute path that is outside the `repo_root` (e.g., `/etc/passwd`).
    -   Assert that `PathSecurityError` is raised.

3.  **`test_normalize_path_symlink_traversal`**:
    -   Create a file outside the `repo_root`.
    -   Create a symlink inside the `repo_root` pointing to the external file.
    -   Pass the path of the symlink to `normalize_path`.
    -   Assert that `PathSecurityError` is raised.

4.  **`test_normalize_path_null_byte_injection`**:
    -   Pass a path containing a null byte (`\x00`).
    -   Assert that `PathSecurityError` is raised.

5.  **`test_normalize_path_legitimate_paths`**:
    -   Pass valid relative and absolute paths that are within the `repo_root`.
    -   Assert that the function returns the correct, normalized relative path without raising an error.
