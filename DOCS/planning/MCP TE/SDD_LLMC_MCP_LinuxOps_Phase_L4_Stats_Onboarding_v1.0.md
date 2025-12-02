# Software Design Document — LLMC MCP LinuxOps Phase L4 (Stats & Onboarding)

Version: v1.0  
Owner: LLMC  
Status: Draft (Ready for implementation)  
Date: 2025-12-01  

---

## 0. Overview

### 0.1 Purpose

Phase L4 extends the LLMC MCP LinuxOps module with:

1. **MCP usage stats tools** so the LLM (and operators) can introspect how tools are being used:
   - `linux.mcp_usage_stats`
   - `linux.mcp_recent_calls`

2. **Onboarding macro tools** that orchestrate small multi-step workflows over LinuxOps/TE:
   - `linux.mcp_run_onboarding` with named flows such as:
     - `organize_downloads`
     - `explain_repo`
     - `system_health`

The intent is to:

- Give the model **self-awareness** about tool usage and performance, without huge context dumps.
- Provide **“one button” operational macros** that encapsulate common tasks into compact, structured results.
- Keep everything **config-driven** and re-usable from agents or human callers.

### 0.2 Scope (Phase L4)

New tools:

- `linux.mcp_usage_stats`
- `linux.mcp_recent_calls`
- `linux.mcp_run_onboarding`

New/extended components:

- `linux_ops.stats` module:
  - Aggregation over structured logs / token audit records.
- `linux_ops.onboarding` module:
  - Flow registry,
  - Core flows implementation.
- Minor additions to docs and configuration.

### 0.3 Non-Goals

- No full BI system or arbitrary analytics query engine.
- No heavyweight workflow engine (onboarding flows are simple Python orchestrations).
- No external monitoring (Prometheus, etc.) — those are handled elsewhere.

---

## 1. Requirements

### 1.1 Functional Requirements — Stats

**Usage Stats**

- R1: `linux.mcp_usage_stats` must return aggregate counts and latency percentiles per MCP tool (at least p95).
- R2: Stats must be **bounded** in time (e.g., “recent window” such as last N hours) to stay relevant and small.
- R3: The tool list must be filterable by prefix (e.g., `linux.` vs all tools) via config.

**Recent Calls**

- R4: `linux.mcp_recent_calls` must return the most recent tool calls (up to `max_results`), ordered newest-first.
- R5: Each record must include:
  - tool name,
  - short argument summary,
  - status (success / error),
  - duration,
  - timestamp.
- R6: Caller can filter by `tool_name` (prefix or exact match).
- R7: `max_results` is bounded (e.g., 200) to avoid bloated responses.

### 1.2 Functional Requirements — Onboarding

**Onboarding Dispatcher**

- R8: `linux.mcp_run_onboarding` must accept a `flow_name` string.
- R9: Dispatcher must map `flow_name` to a Python function implementing that flow.
- R10: Response must be structured as:
  - list of steps (each with description + result),
  - summary string.

**Core Flows**

- R11: `organize_downloads`:
  - Inspect `~/Downloads`,
  - Propose simple folder categories (docs/images/archives/etc.),
  - Optionally move files (dry-run mode support recommended).
- R12: `explain_repo`:
  - Walk the main repo root (from config),
  - Summarize key directories/files and “entry points” for agents,
  - Provide short textual overview.
- R13: `system_health`:
  - Use `linux.sys_snapshot` and possibly process list,
  - Provide short health assessment and any warnings (e.g., high disk use).

### 1.3 Non-Functional Requirements

- **Token Efficiency:**
  - Stats tools: strictly structured, no raw logs.
  - Onboarding flows: 3–10 steps plus short summary — not huge transcripts.
- **Config-Driven:**
  - Time windows for stats, directories for onboarding flows, etc., must be configurable.
- **Safety:**
  - Onboarding flows that modify files (e.g., organize_downloads) must support dry-run and/or require config opt-in.
- **Observability:**
  - Stats tools naturally read the existing observability data; no new heavy infra.

---

## 2. High-Level Design (Phase L4 Slice)

### 2.1 Components

- `llmc_mcp/tools/linux_ops/stats.py`
  - Data access to LLMC metrics/audit store.
  - Aggregation and formatting for MCP.
- `llmc_mcp/tools/linux_ops/onboarding.py`
  - Flow registry: `flow_name -> function`.
  - Flow implementations coordinating LinuxOps tools and TE.
- Existing observability:
  - Structured JSON logs or token audit DB (TokenAuditWriter / structured logging).

### 2.2 Data Sources

Implementation will rely on **existing LLMC observability**. Two primary options:

1. **Token audit DB / store** (preferred):
   - Each record includes:
     - tool name,
     - arguments (or summary),
     - status,
     - duration,
     - timestamp.
2. **Structured JSON logs:**
   - Stats layer may tail or query either:
     - on-disk log files, or
     - a lightweight SQLite/JSON index maintained by LLMC.

Exact source is abstracted behind `stats.py` helpers; SDD mandates an interface rather than a specific backend.

---

## 3. Detailed Design — Types

**File:** `llmc_mcp/tools/linux_ops/types.py`

```python
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class ToolCallRecord:
    tool: str
    args_summary: str
    status: str       # "success" | "error"
    duration_ms: int
    timestamp_iso: str

@dataclass
class ToolUsageStats:
    count: int
    p95_ms: float
    p50_ms: float | None = None  # optional, can be added later
```

---

## 4. Detailed Design — Stats Tools (`stats.py`)

### 4.1 Backend Interface

**File:** `llmc_mcp/tools/linux_ops/stats.py`

We define a small internal abstraction to query recent calls:

```python
from typing import Iterable, Optional
from .types import ToolCallRecord

def iter_recent_tool_calls(
    *,
    window_seconds: int,
    tool_prefix: str | None = None,
    tool_exact: str | None = None,
    max_records: int = 1000,
) -> Iterable[ToolCallRecord]:
    """
    Yield recent ToolCallRecord entries from the underlying observability store.
    Backend may be a DB or structured log; this function hides that detail.
    """
    ...
```

Implementation examples:

- Query a SQLite DB used by TokenAuditWriter.
- Or parse structured logs with a cut-off time and tool filters.

### 4.2 MCP Tool: `linux.mcp_usage_stats`

#### 4.2.1 Purpose

Return per-tool aggregate usage stats for a recent window.

#### 4.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "window_seconds": {
      "type": "integer",
      "minimum": 60,
      "maximum": 86400,
      "default": 3600
    },
    "tool_prefix": {
      "type": ["string", "null"],
      "description": "Restrict to tools with this prefix (e.g., 'linux.')"
    }
  }
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "tools": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "count": { "type": "integer" },
          "p95_ms": { "type": "number" },
          "p50_ms": { "type": ["number", "null"] }
        },
        "required": ["count", "p95_ms"]
      }
    }
  },
  "required": ["tools"]
}
```

#### 4.2.3 Handler Signature

```python
def mcp_linux_mcp_usage_stats(
    window_seconds: int = 3600,
    tool_prefix: str | None = "linux.",
) -> dict:
    ...
```

#### 4.2.4 Implementation Steps

1. **Normalize arguments**
   - Clamp `window_seconds` within allowed range.
2. **Load recent calls**
   - Use `iter_recent_tool_calls(window_seconds=window_seconds, tool_prefix=tool_prefix)`.
3. **Group by tool name**
   - Accumulate durations per tool into a list or running stats.
4. **Compute stats**
   - For each tool:
     - `count = len(durations)`.
     - Compute p95 (and optionally p50) using standard percentile calculation.
   - If few calls (e.g., < 5), still return `count` and approximate p95 from available data.
5. **Return**
   - JSON object mapping `tool -> { count, p95_ms, p50_ms }`.

#### 4.2.5 Error Handling

- If backend is unavailable or throws, return MCP error `"STATS_BACKEND_UNAVAILABLE"` with message.
- If no data is available, return empty `tools` object (not an error).

---

### 4.3 MCP Tool: `linux.mcp_recent_calls`

#### 4.3.1 Purpose

Return a small list of the most recent tool calls.

#### 4.3.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "max_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200,
      "default": 50
    },
    "tool_name": {
      "type": ["string", "null"],
      "description": "Exact tool name or prefix filter (implementation-defined)"
    },
    "window_seconds": {
      "type": "integer",
      "minimum": 60,
      "maximum": 86400,
      "default": 86400
    }
  }
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "records": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tool": { "type": "string" },
          "args_summary": { "type": "string" },
          "status": { "type": "string" },
          "duration_ms": { "type": "integer" },
          "timestamp_iso": { "type": "string" }
        },
        "required": [
          "tool",
          "args_summary",
          "status",
          "duration_ms",
          "timestamp_iso"
        ]
      }
    }
  },
  "required": ["records"]
}
```

#### 4.3.3 Handler Signature

```python
def mcp_linux_mcp_recent_calls(
    max_results: int = 50,
    tool_name: str | None = None,
    window_seconds: int = 86400,
) -> dict:
    ...
```

#### 4.3.4 Implementation Steps

1. Normalize `max_results` and `window_seconds`.
2. Derive prefix/exact filters:
   - If `tool_name` ends with "*", treat it as prefix (e.g., "linux.*").
   - Otherwise treat as exact (or `None` for “all tools”).
3. Call `iter_recent_tool_calls` with appropriate filters.
4. Collect up to `max_results` records, newest-first.
5. For each `ToolCallRecord`, convert to dict with keys:
   - `tool`, `args_summary`, `status`, `duration_ms`, `timestamp_iso`.
6. Return as `{"records": [...]}`.

#### 4.3.5 Error Handling

- Same as `mcp_usage_stats` for backend issues.
- If no data, `records` is an empty list.

---

## 5. Detailed Design — Onboarding Tools (`onboarding.py`)

### 5.1 Flow Registry

**File:** `llmc_mcp/tools/linux_ops/onboarding.py`

```python
from typing import Callable, Dict
from .config import LinuxOpsConfig

OnboardingResult = dict  # JSON-like structure
FlowFunc = Callable[[LinuxOpsConfig, dict | None], OnboardingResult]

_FLOWS: Dict[str, FlowFunc] = {}
```

Helper to register flows:

```python
def register_flow(name: str, func: FlowFunc) -> None:
    _FLOWS[name] = func

def get_flow(name: str) -> FlowFunc | None:
    return _FLOWS.get(name)
```

Registration (at module import time):

```python
def onboarding_organize_downloads(config: LinuxOpsConfig, options: dict | None) -> OnboardingResult:
    ...

def onboarding_explain_repo(config: LinuxOpsConfig, options: dict | None) -> OnboardingResult:
    ...

def onboarding_system_health(config: LinuxOpsConfig, options: dict | None) -> OnboardingResult:
    ...

register_flow("organize_downloads", onboarding_organize_downloads)
register_flow("explain_repo", onboarding_explain_repo)
register_flow("system_health", onboarding_system_health)
```

### 5.2 MCP Tool: `linux.mcp_run_onboarding`

#### 5.2.1 Purpose

Run a named onboarding flow and return its structured report.

#### 5.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "flow_name": { "type": "string" },
    "options": {
      "type": ["object", "null"],
      "additionalProperties": {}
    }
  },
  "required": ["flow_name"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "flow": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "description": { "type": "string" },
          "result": { "type": "string" }
        },
        "required": ["description", "result"]
      }
    },
    "summary": { "type": "string" }
  },
  "required": ["flow", "steps", "summary"]
}
```

#### 5.2.3 Handler Signature

```python
def mcp_linux_mcp_run_onboarding(
    flow_name: str,
    options: dict | None = None,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 5.2.4 Implementation Steps

1. Lookup flow:
   - `flow_func = get_flow(flow_name)`.
   - If `None` → error `"UNKNOWN_FLOW"`.
2. Invoke flow with `config` and `options`.
3. Ensure the result conforms to schema:
   - `{"flow": flow_name, "steps": [...], "summary": ...}`.
4. Return the result.

---

## 6. Onboarding Flow Implementations (Core Set)

### 6.1 `organize_downloads`

#### 6.1.1 Purpose

Give the LLM a structured summary (and optional actions) for cleaning up `~/Downloads`.

#### 6.1.2 Configuration

Add optional config entries:

```toml
[mcp.linux_ops.onboarding]
downloads_dir = "~/Downloads"
organize_downloads_apply_changes = false  # default dry-run
```

#### 6.1.3 Behavior (Dry-Run First)

1. Resolve `downloads_dir` to an absolute path.
2. Use `linux.fs_list` (or TE helper) to collect files (depth 1).
3. Categorize by file extension:
   - docs: `.pdf`, `.docx`, `.txt`, etc.
   - images: `.png`, `.jpg`, `.jpeg`, `.gif`, etc.
   - archives: `.zip`, `.tar`, `.gz`, etc.
   - installers: `.AppImage`, `.deb`, etc.
4. Build a suggested folder structure:
   - `docs/`, `images/`, `archives/`, `other/`.
5. If `organize_downloads_apply_changes` is `true` or `options.apply == true`:
   - Create folders under `downloads_dir`.
   - Move files into categories via `linux.fs_move`.
6. Build `steps` array describing:
   - file counts per category,
   - what would be moved (in dry-run), or what was moved (if applied).

Example step:

```json
{
  "description": "Scanned ~/Downloads",
  "result": "Found 120 files: 40 docs, 30 images, 10 archives, 40 other"
}
```

Summary example:

> "Downloads folder organized into 4 categories. 80 files moved, 40 left in other."

### 6.2 `explain_repo`

#### 6.2.1 Purpose

Give the LLM (and human) a quick structural overview of the main repo.

#### 6.2.2 Configuration

Use existing config:

```toml
[mcp.linux_ops.roots]
allowed_roots = ["~/src/llmc"]
```

Optionally an explicit key:

```toml
[mcp.linux_ops.onboarding]
repo_root = "~/src/llmc"
```

#### 6.2.3 Behavior

1. Resolve `repo_root`.
2. Use `linux.fs_list` with moderate depth (e.g., 2) to get directory tree.
3. Identify key directories/files by simple heuristics:
   - Presence of `pyproject.toml`, `README.md`, `DOCS/`, `tests/`, etc.
4. Build “chapters”:
   - "Core MCP server",
   - "LinuxOps tools",
   - "Docs and configs",
   - "Tests".
5. Steps might include:
   - "Detected Python project with pyproject and tests in `tests/`."
   - "Found MCP tools under `llmc_mcp/tools`."
6. Summary:
   - Short bullet-style description of the repo’s main pieces.

### 6.3 `system_health`

#### 6.3.1 Purpose

Provide a simple operational health check using LLMC MCP tools.

#### 6.3.2 Behavior

1. Call `linux.sys_snapshot`.
2. Optionally call `linux.proc_list` with small `max_results` to find top CPU consumers.
3. Interpret values:
   - If CPU > ~80% → warning.
   - If root disk usage > ~90% → warning.
   - If memory usage > ~85% → warning.
4. Steps:
   - "CPU load measured: 15% with load 0.5/0.4/0.3."
   - "RAM usage: 4/16 GB in use."
   - "Root filesystem: 58% used."
5. Summary:
   - "System healthy" or "High disk usage on /, consider cleanup".

---

## 7. Observability & Error Handling

### 7.1 Logging

Stats tools:

- Log:
  - `window_seconds`,
  - `tool_prefix` / `tool_name`,
  - number of records scanned,
  - number of tools in output.

Onboarding tools:

- Log:
  - `flow_name`,
  - whether changes were applied (for organize_downloads),
  - overall success or error.

### 7.2 Error Codes

Representative MCP error codes:

- Stats:
  - `"STATS_BACKEND_UNAVAILABLE"`
  - `"STATS_QUERY_FAILED"`
- Onboarding:
  - `"UNKNOWN_FLOW"`
  - `"FLOW_EXECUTION_FAILED"`
  - `"FLOW_CONFIG_INVALID"` (e.g., missing path)

---

## 8. Testing Plan

### 8.1 Unit Tests

**File:** `tests/test_linux_ops_stats.py`

- Mock `iter_recent_tool_calls` to return:
  - A mix of tools with different durations and statuses.
- Validate:
  - `mcp_usage_stats` returns correct counts and p95 values.
  - `mcp_recent_calls` respects `max_results`, `tool_name`, and `window_seconds` filters.

**File:** `tests/test_linux_ops_onboarding.py`

- Mock LinuxOps tools (`fs_list`, `fs_move`, `sys_snapshot`, etc.) to avoid real FS/system changes.
- `organize_downloads`:
  - Verify categorization logic and dry-run vs apply behavior.
- `explain_repo`:
  - Mock directory tree to ensure summary generation.
- `system_health`:
  - Mock snapshot and ensure warnings vs “healthy” summary.

### 8.2 Integration Tests

**File:** `tests/integration/test_mcp_linuxops_stats_onboarding.py`

- Ensure stats tools return data on a system with some recorded calls.
- Run `system_health` on a real dev box and check response shape.
- Run `organize_downloads` in dry-run mode in a temp directory with fake data.

---

## 9. Completion Criteria (Phase L4)

Phase L4 is complete when:

1. `linux.mcp_usage_stats`, `linux.mcp_recent_calls`, and `linux.mcp_run_onboarding` are implemented and registered.
2. Core onboarding flows (`organize_downloads`, `explain_repo`, `system_health`) are implemented and wired into the registry.
3. L4 unit tests pass.
4. L4 integration tests pass on a reference Linux environment.
5. Config docs updated with stats/onboarding-related options.
6. `DOCS/mcp_linuxops_tools.md` includes entries for the new tools and flows.

