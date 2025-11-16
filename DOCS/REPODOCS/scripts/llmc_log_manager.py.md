<!--
SOURCE_FILE: scripts/llmc_log_manager.py
SOURCE_HASH: sha256:c66d95334ae72c497a67e31ab18f81ee607cff44ccc0c767dbdaa366d4e4f1ae
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/llmc_log_manager.py – High-Level Overview

**scripts/llmc_log_manager.py** is a utility script providing specific functionality for the LLMC development environment. It automates common tasks and workflows.

## Responsibilities & Behavior (for Humans)

- Defines 1 class(es) for data modeling or service abstraction

## Public Surface Area (API Snapshot)

- `load_logging_config(config_path)`
  Load [logging] config from a TOML file if present.

- `main()`
  Function: main

- `__init__(self, max_size_mb, keep_jsonl_lines, enabled)`
  Function: __init__

- `find_log_files(self, log_dir)`
  Find all log files in directory.

- `get_file_size_info(self, file_path)`
  Get file size and modification info.

- `truncate_log(self, file_path, keep_lines)`
  Truncate log file to last N lines (JSONL) or by size (others).

- `check_logs(self, log_dir)`
  Check all logs and return summary.

- `rotate_logs(self, log_dir)`
  Rotate logs that exceed size limit.

- **LLMCLogManager** (class)
  - Key methods: __init__, find_log_files, get_file_size_info, truncate_log, check_logs
  - Simple log rotation with summary output.


## Data & Schema

### LLMCLogManager

Simple log rotation with summary output.

Parameters:
    max_size_mb: Max size for non-JSONL logs before truncation.
    keep_jsonl_lines: Number of tail lines to keep for JSONL files.
    enabled: Master switch to enable/disable rotation.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `argparse`
- `json`
- `os`
- `pathlib`
- `sys`
- `time`
- `tomllib`
- `typing`


## Configuration & Environment

No specific environment variables detected for this file.

## Error Handling, Edge Cases, and Failure Modes

**Exceptions Raised**:
- `FileNotFoundError` - When required files or directories don't exist
- `ValueError` - For invalid configuration or parameters
- `TimeoutError` - When operations exceed configured timeouts

**Common Failure Modes**:
- Index corruption or missing index files
- LLM provider API failures or rate limits
- Insufficient permissions for file system operations

## Performance & Scaling Notes

This file has no significant performance concerns.

## Security / Footguns

Minimal security risk - primarily internal utility functions.

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 1 class definition(s)
- Contains 8 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = load_logging_config(config_path)
```

