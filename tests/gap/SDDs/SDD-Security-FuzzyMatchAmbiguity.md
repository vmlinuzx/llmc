# SDD: Core Security - Fuzzy Match Ambiguity

## 1. Gap Description

The `normalize_path` function in `llmc/security.py` contains a "fuzzy suffix match" feature. When multiple files in the repository share the same suffix or name, the function resolves this ambiguity by sorting matches first by path length, then alphabetically.

This resolution logic, while deterministic, is not explicitly tested. This is a correctness gap that could become a security issue if a user's intended file is shadowed by another file that the logic prefers. We must have explicit tests to document and lock in this behavior.

## 2. Target Location

The new tests shall be **added** to the existing file: `tests/security/test_security_normalize_path.py`

## 3. Test Strategy

The tests will extend the existing test file by adding new test cases that create an ambiguous situation for the fuzzy matcher. The scenarios will validate the documented sorting logic.

## 4. Implementation Details

The following test cases shall be added to `TestNormalizePath` class in `tests/security/test_security_normalize_path.py`:

1.  **`test_fuzzy_match_resolves_by_shortest_path`**:
    -   Set up a `repo_root` with two files of the same name at different depths:
        -   `repo_root/b/c/ambiguous.txt`
        -   `repo_root/a/ambiguous.txt` (This is the expected resolution)
    -   Call `normalize_path` with `"ambiguous.txt"`.
    -   Assert that the returned path is `a/ambiguous.txt`.

2.  **`test_fuzzy_match_resolves_alphabetically_on_same_length`**:
    -   Set up a `repo_root` with two files of the same name at the same path depth:
        -   `repo_root/z/ambiguous.txt`
        -   `repo_root/x/ambiguous.txt` (This is the expected resolution)
    -   Call `normalize_path` with `"ambiguous.txt"`.
    -   Assert that the returned path is `x/ambiguous.txt`.
