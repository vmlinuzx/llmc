# Software Design Document — LLMC MCP LinuxOps Phase L3 (Interactive Processes / REPLs)

Version: v1.0  
Owner: LLMC  
Status: Draft (Ready for implementation)  
Date: 2025-12-01  

---

## 0. Overview

### 0.1 Purpose

Phase L3 extends the LLMC MCP LinuxOps module with **interactive process / REPL management**, enabling the LLM to:

- Start long-lived shell/REPL processes,
- Send input and read output incrementally,
- Stop processes safely,
- Enforce limits on concurrent processes and timeouts.

This provides Desktop-Commander-style REPL behavior while:

- Assuming the LLM already understands what a REPL is,
- Keeping the MCP surface **small and explicit**,
- Centralizing real work in a **TE process wrapper + registry**,
- Minimizing context bloat via compact, structured outputs.

### 0.2 Scope (Phase L3)

New or extended tools:

- `linux.proc_start`
- `linux.proc_send`
- `linux.proc_read`
- `linux.proc_stop`

Supporting components:

- TE process wrapper and registry (`te.process`).
- Process-related config and enforcement (`LinuxOpsConfig.process_limits`).
- Minimal process bookkeeping/state for safe cleanup.

### 0.3 Non-Goals

- No full terminal emulation (no ANSI parsing, PTY resizing, or cursor control).
- No multi-tenant sandboxing (assumes same Unix user as MCP server).
- No remote container orchestration (local host only).
- No persistence of REPL sessions across MCP server restarts.

---

## 1. Requirements

### 1.1 Functional Requirements

**Start Process / REPL**

- R1: Start an interactive process from a `command` string (e.g. `"python -i"`, `"bash"`, `"node"`).
- R2: Optional `cwd` and `env` overrides.
- R3: Return:
  - a **logical process ID** (`proc_id`),
  - OS PID,
  - initial output (if any),
  - current state (`"running"` or `"exited"`).

**Send Input**

- R4: Accept UTF-8 text input to be sent to the process.
- R5: Input is line-oriented; the tool appends `\n` unless explicitly configured otherwise.

**Read Output**

- R6: Read available stdout/stderr data without hanging.
- R7: Respect a `timeout_ms` argument.
- R8: Return:
  - accumulated output for this read,
  - state: `"running"`, `"exited"`, or `"no_such_process"`.

**Stop Process**

- R9: Terminate a managed process by `proc_id` with a signal (default `TERM`).
- R10: Clean up registry state; safe to call multiple times (idempotent best-effort).

**Process Limits & Safety**

- R11: Enforce `process_limits.max_procs_per_session` and `max_procs_total` on `proc_start`.
- R12: Track `start_time` and `last_activity` timestamps per process.
- R13: Optionally auto-cleanup stale processes (best-effort; triggered on new operations).
- R14: Disallow starting processes entirely if `features.repl_enabled` is `false`.

### 1.2 Non-Functional Requirements

- **Responsiveness:** `proc_read` must return within the requested timeout plus small overhead.
- **Resource Control:** No unbounded process creation; registry protects from runaways.
- **Token Efficiency:**
  - `proc_read` returns relatively small chunks; clients may call it repeatedly.
  - No echoing of large historical logs; this is not a transcript store.
- **Observability:** All operations are logged and counted in metrics/audit trails.

---

## 2. High-Level Design (Phase L3 Slice)

### 2.1 Components

- `llmc_mcp/te/process.py` — TE process wrapper and registry:
  - Process launch, I/O, stop.
  - In-memory registry keyed by `proc_id`.
- `llmc_mcp/tools/linux_ops/proc.py` — MCP tool handlers:
  - `mcp_linux_proc_start`
  - `mcp_linux_proc_send`
  - `mcp_linux_proc_read`
  - `mcp_linux_proc_stop`
- `llmc_mcp/tools/linux_ops/config.py` — process limits & feature flags:
  - `LinuxOpsProcessLimits`
  - `LinuxOpsFeatureFlags`
- `llmc_mcp/tools/linux_ops/types.py`:
  - `ManagedProcess` (TE-level internal type; not usually exposed directly).

### 2.2 Data Flow Example — REPL session

1. `linux.proc_start` called with `{"command": "python -i", "cwd": "~/src/llmc"}`.
2. Handler checks `repl_enabled`, process limits:
   - counts managed processes for current session and globally.
3. Handler calls `te.process.start_process(...)`.
4. TE layer:
   - `subprocess.Popen` with pipes,
   - builds a `ManagedProcess` entry and adds it to registry.
5. Handler reads initial output (with short timeout) and returns:
   - `{"proc_id": "...", "pid": 12345, "first_output": "Python ...", "state": "running"}`.
6. Subsequent calls:
   - `linux.proc_send` writes commands to stdin.
   - `linux.proc_read` polls stdout/stderr and returns output/state.
7. `linux.proc_stop` issues termination, cleans up registry entry.

---

## 3. TE Process Wrapper & Registry

### 3.1 Data Structures

**File:** `llmc_mcp/te/process.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import subprocess
import time
import uuid

@dataclass
class ManagedProcess:
    proc_id: str
    pid: int
    command: str
    cwd: str
    start_time: float
    last_activity: float
    p: subprocess.Popen = field(repr=False)
```

The registry is a simple in-memory dictionary:

```python
_REGISTRY: Dict[str, ManagedProcess] = {}
```

No persistence across restarts; processes are best-effort cleaned up by the OS.

### 3.2 API Surface

```python
def start_process(
    command: str,
    cwd: Optional[str],
    env: Optional[dict],
) -> ManagedProcess:
    ...

def send_input(proc_id: str, data: str) -> None:
    ...

def read_output(proc_id: str, timeout_sec: float) -> tuple[str, str]:
    ...
    # Return (output, state) where state is 'running', 'exited', or 'no_such_process'.
def stop_process(proc_id: str, signal_name: str = "TERM") -> None:
    ...

def list_managed_processes() -> list[ManagedProcess]:
    ...
```

### 3.3 Implementation Details

**start_process**

- Use `shlex.split(command)` to build argv.
- Spawn with `subprocess.Popen`:
  - `stdin=subprocess.PIPE`,
  - `stdout=subprocess.PIPE`,
  - `stderr=subprocess.STDOUT`,
  - `text=True`,
  - optional `cwd` and `env`.
- Create `proc_id` = `P_<timestamp>_<uuid4().hex[:8]>`.
- Add to `_REGISTRY`.
- Set `start_time` and `last_activity` to `time.time()`.

**send_input**

- Lookup `ManagedProcess` by `proc_id`. If missing → raise `ProcessNotFoundError`.
- Write `data + "\n"` to `p.stdin` and flush.
- Update `last_activity`.

**read_output**

- Lookup process; if missing → `("", "no_such_process")`.
- Use non-blocking read pattern:
  - Either:
    - `select`/`poll` on `p.stdout.fileno()`, or
    - `readline` in a loop until timeout.
- Accumulate output into a string; update `last_activity` if any bytes read.
- Determine state:
  - `p.poll()` is `None` → `"running"`,
  - else `"exited"`.

**stop_process**

- Lookup process; if missing, just return (idempotent).
- Map `signal_name` (`"TERM"`, `"KILL"`, `"INT"`, `"HUP"`) to `signal.SIG*`.
- Send signal; optionally wait for short timeout and force-kill if still running.
- Remove from `_REGISTRY`.

**list_managed_processes**

- Return a snapshot (shallow copies) for metrics/logging.

**Auto-cleanup (optional)**

- Each entry has `last_activity`. When:
  - starting a new process,
  - listing managed processes,
  - or reading output,
- Optionally prune entries whose `last_activity` is older than a configured TTL (e.g., 1 hour).

---

## 4. MCP Tool Design — Signatures & Schemas

### 4.1 MCP Tool: `linux.proc_start`

#### 4.1.1 Purpose

Start a managed interactive process and return its logical ID, OS PID, and initial output.

#### 4.1.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "command": { "type": "string" },
    "cwd": { "type": ["string", "null"], "description": "Optional working directory" },
    "env": {
      "type": ["object", "null"],
      "additionalProperties": { "type": "string" },
      "description": "Optional environment variable overrides"
    },
    "initial_read_timeout_ms": {
      "type": "integer",
      "minimum": 0,
      "maximum": 5000,
     default": 1000
    }
  },
  "required": ["command"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "proc_id": { "type": "string" },
    "pid": { "type": "integer" },
    "first_output": { "type": "string" },
    "state": { "type": "string", "enum": ["running", "exited"] }
  },
  "required": ["proc_id", "pid", "first_output", "state"]
}
```

#### 4.1.3 Handler Signature

**File:** `llmc_mcp/tools/linux_ops/proc.py`

```python
def mcp_linux_proc_start(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    initial_read_timeout_ms: int = 1000,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.1.4 Implementation Steps

1. **Feature flag check**
   - If `not config.features.repl_enabled`, return `"FEATURE_DISABLED"` error.

2. **Process limit enforcement**
   - Count processes in `_REGISTRY` overall and (optionally) by session (session identity derived from env or LLMC_TE_SESSION_ID or similar).
   - If limits exceeded → return error `"PROC_LIMIT_EXCEEDED"` with a helpful message.

3. **Command validation**
   - Optionally check binary against `config.commands.allowed_binaries` / `unsafe_binaries`.
   - If disallowed → `"COMMAND_NOT_ALLOWED"`.

4. **Start process**
   - Call `te.process.start_process(command, cwd, env)`.

5. **Initial output**
   - Call `te.process.read_output(proc_id, initial_read_timeout_ms / 1000.0)` to grab first chunk.

6. **Return payload**
   - `proc_id`, `pid`, `first_output`, `state`.

---

### 4.2 MCP Tool: `linux.proc_send`

#### 4.2.1 Purpose

Send a line of input to a managed process.

#### 4.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "proc_id": { "type": "string" },
    "input": { "type": "string" }
  },
  "required": ["proc_id", "input"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "acknowledged": { "type": "boolean" }
  },
  "required": ["acknowledged"]
}
```

#### 4.2.3 Handler Signature

```python
def mcp_linux_proc_send(
    proc_id: str,
    input: str,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.2.4 Implementation Steps

1. Optionally check `repl_enabled`.
2. Call `te.process.send_input(proc_id, input)`.
3. If process not found → `"PROCESS_NOT_FOUND"`.
4. On success, return `{"acknowledged": true}`.

---

### 4.3 MCP Tool: `linux.proc_read`

#### 4.3.1 Purpose

Read available output from a managed process with a bounded timeout.

#### 4.3.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "proc_id": { "type": "string" },
    "timeout_ms": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10000,
      "default": 1000
    }
  },
  "required": ["proc_id"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "output": { "type": "string" },
    "state": {
      "type": "string",
      "enum": ["running", "exited", "no_such_process"]
    }
  },
  "required": ["output", "state"]
}
```

#### 4.3.3 Handler Signature

```python
def mcp_linux_proc_read(
    proc_id: str,
    timeout_ms: int = 1000,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.3.4 Implementation Steps

1. Optional feature flag check.
2. Call `te.process.read_output(proc_id, timeout_ms / 1000.0)` to get `(output, state)`.
3. Return JSON payload.

---

### 4.4 MCP Tool: `linux.proc_stop`

#### 4.4.1 Purpose

Terminate a managed process and clean up registry state.

#### 4.4.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "proc_id": { "type": "string" },
    "signal": {
      "type": "string",
      "enum": ["TERM", "KILL", "INT", "HUP"],
      "default": "TERM"
    }
  },
  "required": ["proc_id"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "message": { "type": "string" }
  },
  "required": ["success", "message"]
}
```

#### 4.4.3 Handler Signature

```python
def mcp_linux_proc_stop(
    proc_id: str,
    signal: str = "TERM",
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.4.4 Implementation Steps

1. Optional feature flag check.
2. Call `te.process.stop_process(proc_id, signal_name=signal)`.
3. If no such process, return `{"success": false, "message": "No such proc_id"}`.
4. If success, return `{"success": true, "message": "Sent SIGTERM to proc_id ..."}` (respect actual signal string).

---

## 5. Configuration & Limits

### 5.1 Process Limits

**File:** `llmc_mcp/tools/linux_ops/config.py`

Already introduced in L2; for L3 we emphasize:

```python
@dataclass
class LinuxOpsProcessLimits:
    max_procs_per_session: int = 4
    max_procs_total: int = 32
    default_timeout_sec: int = 60
    max_timeout_sec: int = 600
    allow_kill_other_users: bool = False
```

- `max_procs_per_session`:
  - Bound on processes that share a session ID (coming from LLMC_TE_SESSION_ID or equivalent).
- `max_procs_total`:
  - Bound across all sessions.

### 5.2 Feature Flags

```python
@dataclass
class LinuxOpsFeatureFlags:
    fs_enabled: bool = True
    proc_enabled: bool = True
    repl_enabled: bool = True
    system_enabled: bool = True
```

- L3 respects `repl_enabled`; if false, `proc_start/send/read/stop` return `"FEATURE_DISABLED"`.

---

## 6. Observability & Error Handling

### 6.1 Logging

Each L3 handler logs at INFO:

- `linux.proc_start`:
  - `command`, `cwd`, `proc_id`, `pid`, `initial_output_len`, duration.
- `linux.proc_send`:
  - `proc_id`, `input_len`, outcome.
- `linux.proc_read`:
  - `proc_id`, `timeout_ms`, `output_len`, `state`.
- `linux.proc_stop`:
  - `proc_id`, `signal`, success/failure.

### 6.2 Metrics

- Counters:
  - per-tool call counts.
- Histograms:
  - per-tool latency.
- Gauges:
  - current managed processes count,
  - per-session process count.

### 6.3 Error Codes

Representative errors:

- `"FEATURE_DISABLED"` — repl tools disabled via config.
- `"PROC_LIMIT_EXCEEDED"` — hitting process limits.
- `"PROCESS_NOT_FOUND"` — unknown `proc_id` (for send/read).
- `"STOP_FAILED"` — stop call encountered OS-level issues.

---

## 7. Testing Plan

### 7.1 Unit Tests

**File:** `tests/test_linux_ops_proc_repl.py`

Scenarios:

- `proc_start`:
  - Respect `repl_enabled` (disabled → error).
  - Exceeding `max_procs_per_session` and `max_procs_total`.
  - Command allowed vs disallowed via `LinuxOpsCommands`.
- `proc_send`:
  - Unknown proc_id → `"PROCESS_NOT_FOUND"`.
  - Happy path (mock TE process).
- `proc_read`:
  - Unknown proc_id → state `"no_such_process"`.
  - Running vs exited state mapping.
  - Respect timeout; no hang.
- `proc_stop`:
  - Unknown proc_id is handled gracefully.
  - Successful termination.

Unit tests will **mock** `te.process` functions to avoid real process spawning in most cases.

### 7.2 Integration Tests

**File:** `tests/integration/test_mcp_linuxops_repl.py`

Integration scenarios (on a Linux dev box):

- Start a simple REPL:
  - Command: `"python -i"` or `"bash"`.
  - Verify `proc_id`, `pid`, initial prompt in `first_output`.
- Send input:
  - e.g., `print("hi")` or `echo hi`.
- Read output:
  - Confirm the expected text appears.
- Stop:
  - Verify the process is no longer listed in registry or system.

Guardrails:

- Use short-lived REPLs.
- Ensure cleanup is performed at test teardown even if assertions fail.

---

## 8. Risks and Mitigations

- **Risk:** Orphaned processes if MCP crashes.
  - **Mitigation:** 
    - Use simple processes that naturally exit,
    - Document this as an operational consideration,
    - Provide admin tooling (outside scope here) to inspect and clean up.

- **Risk:** Infinite loops or runaway REPLs consuming CPU.
  - **Mitigation:**
    - Process limits (`max_procs_*`),
    - Encourage conservative timeouts and careful REPL use,
    - (Optional future work) CPU usage checks and auto-kill.

- **Risk:** Excessive output from REPL flooding tokens.
  - **Mitigation:**
    - `proc_read` returns bounded chunks and avoids storing history,
    - Callers must explicitly loop for more output.

---

## 9. Completion Criteria (Phase L3)

Phase L3 is considered complete when:

1. `linux.proc_start/send/read/stop` are implemented and registered.
2. TE process wrapper and registry are implemented and used exclusively (no ad-hoc `Popen` calls in tools).
3. L3 unit tests pass consistently.
4. L3 integration tests pass on a reference Linux environment.
5. Config docs updated to describe REPL-related flags and process limits.
6. Basic metrics and logs for REPL tools are visible in LLMC observability stack.

