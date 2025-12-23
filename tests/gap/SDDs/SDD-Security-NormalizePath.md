# SDD: Path Traversal and Null Byte Injection in normalize_path

## 1. Gap Description
The `normalize_path` function in `llmc/security.py` is a critical security component that prevents path traversal attacks. However, there are no specific tests for several potential vulnerabilities, including:
- Null byte injection (`\x00`) in the target path.
- Absolute path traversal (`/etc/passwd`).
- Path traversal with `../`.
- Malicious input in the fuzzy suffix matching logic.

This SDD describes the tests required to validate these security controls.

## 2. Target Location
`tests/security/test_security.py`

## 3. Test Strategy
The tests will use `pytest` to assert that the `normalize_path` function raises a `PathSecurityError` when presented with malicious input. The tests will cover the following scenarios:
- **Null Byte Injection:** Pass a path containing a null byte and verify that a `PathSecurityError` is raised.
- **Absolute Path Traversal:** Pass an absolute path outside the repository root and verify that a `PathSecurityError` is raised.
- **Path Traversal:** Pass a relative path that attempts to traverse outside the repository root and verify that a `PathSecurityError` is raised.
- **Fuzzy Suffix Matching with Malicious Input:** Pass a malicious path to the fuzzy suffix matching logic and verify that it does not lead to a path outside the repository root.

## 4. Implementation Details
The test implementation will require the following:
- A new test file `tests/security/test_security.py`.
- A `pytest` fixture to create a temporary repository root for testing.
- A test case for each of the scenarios described in the Test Strategy.
- Assertions that the `normalize_path` function raises a `PathSecurityError` for each malicious input.
