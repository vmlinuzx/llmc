# SDD: ConfigManager Robustness & Error Handling

## 1. Gap Description
The `ConfigManager` class in `llmc/config/manager.py` handles reading and writing the critical `llmc.toml` configuration file. While it has basic backup logic, it lacks comprehensive tests for failure scenarios:
- **Write Failures**: What happens if the disk is full or permissions are denied during `save()`?
- **Backup Failures**: What if creating the backup fails? Does the original file stay intact?
- **Restoration Failures**: If the write fails, does the fallback restoration actually work? What if the backup is also corrupted?
- **Concurrency**: There is no locking mechanism, so concurrent writes (e.g., from a daemon and a CLI user) could corrupt the file.

The current implementation uses `shutil.copy` and `tomli_w.dump` without verifying success before switching the internal state.

## 2. Target Location
`tests/gap/test_config_robustness.py`

## 3. Test Strategy
We need to simulate system-level failures using `unittest.mock`.

### Scenarios to Test:
1.  **Happy Path**: Verify `save()` creates a backup and writes the new file correctly.
2.  **Backup Failure**: Mock `shutil.copy` to raise `PermissionError`. Verify `save()` aborts **before** touching the original file.
3.  **Write Failure (Disk Full)**: Mock `open` or `tomli_w.dump` to raise `OSError` (e.g., ENOSPC). Verify that:
    - The exception is raised.
    - The backup file exists.
    - The original file is restored from backup (or never touched if we change the implementation to write to temp first).
    - The internal `self.config` state is NOT updated (or reverted).
4.  **Restoration Failure**: Simulate a write failure followed by a restoration failure (e.g., backup deleted). Verify the error message clearly indicates the catastrophic failure.
5.  **Concurrency (File Locking)**: Since we can't easily add a file lock in the test without changing the code, we should at least verify that `save` is not atomic and identify it as a known risk in the test comments (or test a proposed locking mechanism if we decide to implement one). *For now, focus on error handling.*

## 4. Implementation Details
- Use `pytest`.
- Use `tmp_path` fixture to create a real temporary config file for each test.
- Use `unittest.mock.patch` to inject faults.
- **Do not** modify the production code (`llmc/config/manager.py`) yet. We are *characterizing* the gap. The test should expose the fragility (some tests might fail if the current code is buggy, which is the point).

**Note**: The current `save` implementation does `backup()` -> `write()` -> `restore if fail`. This is "optimistic" but risky. The test should verify if this logic holds up.
