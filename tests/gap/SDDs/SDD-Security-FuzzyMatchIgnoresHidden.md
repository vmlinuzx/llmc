# SDD: Fuzzy Match Hidden Directory Exclusion

## 1. Gap Description
The `llmc.security.normalize_path` function includes a "fuzzy suffix match" feature. This feature has logic to explicitly ignore files located in hidden directories (e.g., `.git`, `.vscode`) and common artifact directories (`venv`, `__pycache__`, `node_modules`).

Currently, there are no tests that verify this exclusion mechanism. A regression in this logic could cause the function to incorrectly resolve a path to a sensitive or unintended file within one of these ignored directories.

## 2. Target Location
The new test should be added to the existing test file for this function: `tests/security/test_security_normalize_path.py`.

## 3. Test Strategy
The test will create a temporary repository structure containing a target file in a standard directory and a file with the same name in a hidden directory (e.g., `.git/hooks/`). It will then call `normalize_path` with the ambiguous filename and assert that the function correctly resolves to the file in the standard directory, effectively ignoring the one in the hidden directory.

This process should be repeated for other ignored directory names like `venv`, `__pycache__`, and `node_modules`.

## 4. Implementation Details
- Use the `tmp_path` fixture from `pytest`.
- Create a directory structure like the following:
  ```
  /repo
  ├── .git/
  │   └── config
  ├── src/
  │   └── config
  └── venv/
      └── config
  ```
- Call `normalize_path(repo_root, "config")`.
- Assert that the returned path is `src/config`.
- The test should be named `test_fuzzy_match_ignores_hidden_and_artifact_directories`.
- The test should be comprehensive enough to cover `.startswith('.')`, `venv`, `__pycache__`, and `node_modules`.
