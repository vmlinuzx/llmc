<!--
SOURCE_FILE: scripts/router.py
SOURCE_HASH: sha256:c3ec1237f28da4a05e9354eed978f9209d8768aa31aaecf2eb881d39b9d303ee
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/router.py – High-Level Overview

**scripts/router.py** is a utility script providing specific functionality for the LLMC development environment. It automates common tasks and workflows.

## Responsibilities & Behavior (for Humans)

- Defines 1 class(es) for data modeling or service abstraction

## Public Surface Area (API Snapshot)

- `estimate_tokens_from_text(text)`
  Rough token estimate (~4 characters per token).

- `_walk_json(obj, depth)`
  Return (node_count, max_depth) for parsed JSON objects.

- `estimate_json_nodes_and_depth(text)`
  Estimate number of JSON nodes and depth from text.

- `estimate_nesting_depth(snippet)`
  Estimate generic nesting depth using braces/brackets/parentheses.

- `expected_output_tokens(span)`
  Estimate output tokens for enrichment JSON response.

- `detect_truncation(output_text, max_tokens_used, finish_reason)`
  Heuristically detect truncated JSON output.

- `choose_start_tier(metrics, settings, override)`
  Choose initial tier based on metrics and overrides.

- `choose_next_tier_on_failure(failure_type, current_tier, metrics, settings, promote_once)`
  Function: choose_next_tier_on_failure

- `classify_failure(failure)`
  Function: classify_failure

- `clamp_usage_snippet(result, max_lines)`
  Function: clamp_usage_snippet

- **RouterSettings** (class)
  - Key methods: __post_init__, effective_token_limit
  - Tunable thresholds for routing decisions.


## Data & Schema

### RouterSettings

Tunable thresholds for routing decisions.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `dataclasses`
- `json`
- `math`
- `os`
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
- Contains 12 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = estimate_tokens_from_text(text)
```

