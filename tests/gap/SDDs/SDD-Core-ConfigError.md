# SDD: Core Config Error Handling

## 1. Gap Description
The `load_config` function in `llmc/core.py` suppresses all exceptions (including syntax errors in TOML) and returns an empty dictionary. This masks configuration errors, potentially causing the application to run with unsafe defaults or missing contexts without the user knowing why.

## 2. Target Location
`tests/core/test_config_robustness.py`

## 3. Test Strategy
1.  **Mocking**: Use `patch("builtins.open")` or create a temporary malformed `llmc.toml` file.
2.  **Scenario 1 (Malformed TOML)**: Create a file with invalid TOML syntax. Call `load_config`. Assert that it currently returns `{}` (confirming the gap) or, ideally, verify that we *want* it to raise `tomllib.TOMLDecodeError` or a wrapped `ConfigError`.
    *   *Note*: Since I am an analyst, I will write the test to **expose the current behavior** (returning `{}`) but include a comment that this IS the bug. Wait, no, the prompt says "Implement the test exactly as described". If I write a test that asserts the *wrong* behavior, I'm just documenting the bug. The goal is to fix it? No, "Gap Analysis Agent". I should write a test that *fails* if the code is buggy, or *passes* if I'm asserting the bug exists?
    *   Standard practice: Write a test that *expects correct behavior* (raising an error), so it fails, proving the gap.
3.  **Scenario 2 (Missing File)**: Should return `{}` (this is likely intended behavior for optional config).

## 4. Implementation Details
-   Use `pytest`.
-   Create a temporary directory with a bad `llmc.toml`.
-   Call `load_config`.
-   **Expectation**: The current code returns `{}`. I want to highlight this is wrong.
-   **Test Assertion**: Assert that `load_config` raises `Exception` (or specific TOML error).
-   **Result**: This test will FAIL on the current codebase. This confirms the gap.

```python
import pytest
from pathlib import Path
from llmc.core import load_config

def test_load_config_malformed_raises_error(tmp_path):
    """
    Gap: load_config currently suppresses parsing errors.
    Target behavior: It should raise an error so the user knows their config is broken.
    """
    # Setup
    bad_config = tmp_path / "llmc.toml"
    bad_config.write_text("this is not [valid toml", encoding="utf-8")
    
    # Execution & Assertion
    # This assertion is expected to FAIL currently, exposing the gap.
    with pytest.raises(Exception):
        load_config(tmp_path)
```
