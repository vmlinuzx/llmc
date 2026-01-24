# SDD: RAG Skeletonizer Test Coverage

## 1. Gap Description

The `llmc/rag/skeleton.py` module, which generates structural summaries of code, has no test coverage. This is a high-risk gap, as bugs in the skeletonization process can lead to flawed context for the LLM, degrading the quality of RAG-based responses.

## 2. Target Location

A **new test file** shall be created at: `tests/rag/test_skeleton.py`.

## 3. Test Strategy

The testing will be based on `pytest` and will be data-driven. A series of Python code snippets, representing various language features, will be defined. For each snippet, the `Skeletonizer` will be run, and its output will be compared against a pre-defined "expected" skeleton.

- **Parametrization:** `pytest.mark.parametrize` will be used to create a test case for each (input_code, expected_skeleton) pair. This makes it easy to add new test cases in the future.
- **Fixtures:** A pytest fixture will provide an instance of the `Skeletonizer`.
- **File System Mocks:** For testing `generate_repo_skeleton`, the `pyfakefs` library or a temporary directory created with `tmp_path` will be used to simulate a repository structure with multiple files.

## 4. Implementation Details

### 4.1. `Skeletonizer` Class Tests

The core of the testing will be a parametrized test function.

```python
# In tests/rag/test_skeleton.py

import pytest
from llmc.rag.skeleton import Skeletonizer

TEST_CASES = [
    # Each item is a tuple: (id, input_code, expected_skeleton)

    (
        "simple_function",
        """
def hello(name: str) -> str:
    """A simple function."""
    print(f"Hello, {name}")
    return f"Hello, {name}"
        """,
        """
def hello(name: str) -> str:
    """A simple function."""
    ...
        """.strip()
    ),

    (
        "async_function",
        """
async def fetch_data(session):
    print("fetching")
    async with session.get('http://python.org') as response:
        return await response.text()
        """,
        """
async def fetch_data(session):
    ...
        """.strip()
    ),

    (
        "simple_class",
        """
class Greeter:
    """A simple class."""
    def __init__(self, greeting: str):
        self.greeting = greeting

    def greet(self, name: str):
        """Greet someone."""
        return f"{self.greeting}, {name}"
        """,
        """
class Greeter:
    """A simple class."""
    def __init__(self, greeting: str):
        ...

    def greet(self, name: str):
        """Greet someone."""
        ...
        """.strip()
    ),

    (
        "decorated_function",
        """
import functools

@functools.lru_cache(maxsize=128)
def fib(n):
    if n < 2:
        return n
    return fib(n-1) + fib(n-2)
        """,
        """
@functools.lru_cache(maxsize=128)
def fib(n):
    ...
        """.strip()
    ),

    # TODO: Add more test cases for:
    # - Class with inheritance
    # - Class with class variables
    # - Function with complex signature (*args, **kwargs, /)
    # - File with only imports
    # - Empty file
    # - File with top-level assignments (should be skipped)
]

@pytest.mark.parametrize("test_id, code, expected", TEST_CASES)
def test_skeletonizer(test_id, code, expected):
    source_bytes = code.encode("utf-8")
    skeleton = Skeletonizer(source_bytes, "python").skeletonize()
    # Normalize whitespace/newlines for comparison
    assert "\n".join(s.strip() for s in skeleton.strip().splitlines()) == "\n".join(s.strip() for s in expected.strip().splitlines())

```

### 4.2. `generate_repo_skeleton` Function Tests

These tests require mocking the filesystem.

- **`test_repo_skeleton_basic`**:
  - Create a fake directory structure with `tmp_path`:
    - `my_repo/main.py` (with some content)
    - `my_repo/utils.py` (with some content)
    - `my_repo/README.md` (should be ignored)
  - Run `generate_repo_skeleton` on the `my_repo` path.
  - Assert that the output string contains skeletonized versions of `main.py` and `utils.py`.
  - Assert that the output does NOT contain content from `README.md`.
- **`test_repo_skeleton_empty_repo`**:
  - Run on an empty directory.
  - Assert the output is generated correctly with "File Count: 0".
- **`test_repo_skeleton_non_existent_repo`**:
  - Run on a path that doesn't exist.
  - Assert that it raises a `FileNotFoundError` or handles it gracefully.
- **`test_repo_skeleton_file_read_error`**:
  - Use `pyfakefs` to create a file that raises an error on `read_bytes`.
  - Assert that the error is caught and logged in the output string, as per the implementation.

### 4.3. Other Cases
- **Test Non-Python Language**:
  - Input a Javascript snippet with `lang="javascript"`.
  - Assert that the `skeletonize` method returns the original source code decoded, as per the fallback logic.

## 5. Recommended Executor

**Demon:** `rem_worker` (Standard Test Implementation Worker)
**Reason:** This is a standard test implementation task requiring `pytest` and data-driven testing patterns.

```
