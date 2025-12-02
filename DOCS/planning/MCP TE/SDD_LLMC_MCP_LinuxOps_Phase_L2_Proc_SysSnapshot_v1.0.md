# Software Design Document — LLMC MCP LinuxOps Phase L2 (Process & System Snapshot)

Version: v1.0  
Owner: LLMC  
Status: Draft (Ready for implementation)  
Date: 2025-12-01  

---

## 0. Overview

### 0.1 Purpose

Phase L2 extends the LLMC MCP LinuxOps module with **process inspection/control** and **system snapshot** capabilities:

- Process tools:
  - `linux.proc_list`
  - `linux.proc_kill`
- System tools:
  - `linux.sys_snapshot`
  - (Optional) `linux.sys_services`, `linux.sys_logs` for richer snapshots

The design aims to:

- Match Desktop Commander’s operational visibility for Linux,
- Maintain **strict safety** (no wild `kill -9` of critical system processes),
- Keep **responses compact** and task-focused, with summary-first output,
- Integrate with LLMC’s existing **config, logging, metrics, and audit** paths.

### 0.2 Goals

- Allow the model to:
  - Inspect running processes and resource usage,
  - Safely terminate processes in a controlled way,
  - Retrieve a concise system health snapshot (CPU, RAM, disk, load).
- Enforce:
  - Safe process kill rules,
  - Reasonable result bounds and summarization.

### 0.3 Non-Goals

- No full-featured job scheduler or service manager.
- No container orchestration controls (Docker/Kubernetes).
- No editing of system config files in this phase.
- System logs and services are **optional**, controlled via configuration and potentially deferred.

---

## 1. Requirements

### 1.1 Functional Requirements

**Process Listing**

- R1: Return a list of current processes with, at minimum:
  - PID,
  - user,
  - CPU%,
  - MEM%,
  - command.
- R2: Support a `max_results` parameter and truncate results when necessary.
- R3: Provide stable, machine-friendly fields suitable for filtering/sorting on the client side.

**Process Kill**

- R4: Send a signal (default: `SIGTERM`) to a specific PID.
- R5: Enforce guardrails:
  - Do not allow killing PID 1.
  - Do not allow killing the MCP server process itself.
  - Optionally disallow killing processes owned by other users unless configured.
- R6: Return a clear status and message.

**System Snapshot**

- R7: Provide a concise snapshot of:
  - CPU usage (percentage),
  - load average (1/5/15),
  - memory usage (used / total),
  - disk usage per major mount.
- R8: Provide a short human-readable summary, plus structured data.
- R9: Use `psutil` if available, otherwise shell fallbacks.

**Optional: System Services & Logs**

- R10 (optional): List active services (e.g., via `systemctl`).
- R11 (optional): Retrieve a bounded tail of system logs.

### 1.2 Non-Functional Requirements

- **Performance:** All tools should return within ~500 ms under normal load on a typical dev machine.
- **Safety:** 
  - No process killing without clear constraints.
  - No excessive disclosure of other users’ processes unless explicitly enabled.
- **Token Efficiency:**
  - `proc_list` should default to a small `max_results` (e.g., 100) with the ability to ask for more.
  - `sys_snapshot` must be small and structured.
- **Observability:**
  - Log tool usage, durations, errors.
  - Feed into LLMC metrics and audit trail.

---

## 2. High-Level Design (Phase L2 Slice)

### 2.1 Components

Phase L2 primarily exercises:

- `LinuxOpsConfig` (process/safety-related fields),
- Process inspection implementation (`proc.py`),
- System snapshot implementation (`sysinfo.py`),
- TE utilities where applicable (for shell/system fallback),
- MCP server registration additions.

### 2.2 Data Flow

Example for `linux.proc_kill`:

1. MCP client calls `linux.proc_kill` with `{ "pid": 1234, "signal": "TERM" }`.
2. MCP server dispatches to `mcp_linux_proc_kill`.
3. Handler:
   - Checks allowed operations from `LinuxOpsConfig`.
   - Validates that PID is not 1 or the MCP server PID.
   - Optionally checks process owner.
   - Executes `os.kill` with appropriate signal.
4. Handler returns JSON with:
   - `{ "success": true, "message": "Sent SIGTERM to pid 1234" }`.
5. Metrics and logs capture duration and outcome.

---

## 3. Detailed Design — Config (Phase L2 Extensions)

### 3.1 Process Limits and Safety

**File:** `llmc_mcp/tools/linux_ops/config.py`

Extend `LinuxOpsConfig` with process-related configuration:

```python
from dataclasses import dataclass, field
from typing import Set

@dataclass
class LinuxOpsProcessLimits:
    max_procs_per_session: int = 4
    max_procs_total: int = 32
    default_timeout_sec: int = 60
    max_timeout_sec: int = 600
    allow_kill_other_users: bool = False

@dataclass
class LinuxOpsFeatureFlags:
    fs_enabled: bool = True
    proc_enabled: bool = True
    repl_enabled: bool = True
    system_enabled: bool = True

@dataclass
class LinuxOpsCommands:
    allowed_binaries: Set[str] = field(default_factory=set)
    unsafe_binaries: Set[str] = field(default_factory=set)
    allow_unsafe: bool = False

@dataclass
class LinuxOpsConfig:
    roots: LinuxOpsRoots = field(default_factory=LinuxOpsRoots)
    commands: LinuxOpsCommands = field(default_factory=LinuxOpsCommands)
    process_limits: LinuxOpsProcessLimits = field(default_factory=LinuxOpsProcessLimits)
    features: LinuxOpsFeatureFlags = field(default_factory=LinuxOpsFeatureFlags)
```

**TOML Example:**

```toml
[mcp.linux_ops.process_limits]
max_procs_per_session = 4
max_procs_total = 32
default_timeout_sec = 60
max_timeout_sec = 600
allow_kill_other_users = false

[mcp.linux_ops.features]
proc_enabled = true
system_enabled = true
```

---

## 4. Detailed Design — Process Tools (`proc.py`)

### 4.1 Shared Types

**File:** `llmc_mcp/tools/linux_ops/types.py`

```python
from dataclasses import dataclass

@dataclass
class ProcessInfo:
    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    command: str
```

### 4.2 MCP Tool: `linux.proc_list`

#### 4.2.1 Purpose

Return a bounded list of running processes with key resource usage details.

#### 4.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "max_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5000,
      "default": 200
    },
    "user": {
      "type": ["string", "null"],
      "description": "Optional username filter"
    }
  }
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "processes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "pid": { "type": "integer" },
          "user": { "type": "string" },
          "cpu_percent": { "type": "number" },
          "mem_percent": { "type": "number" },
          "command": { "type": "string" }
        },
        "required": ["pid", "user", "command"]
      }
    },
    "total_processes": { "type": "integer" },
    "truncated": { "type": "boolean" }
  },
  "required": ["processes", "total_processes", "truncated"]
}
```

#### 4.2.3 Handler Signature

```python
def mcp_linux_proc_list(
    *,
    config: LinuxOpsConfig,
    max_results: int = 200,
    user: str | None = None,
) -> dict:
    ...
```

#### 4.2.4 Implementation Strategy

Option A (preferred): use `psutil` if installed.  
Option B (fallback): parse `ps` command output.

**Psutil path (pseudo):**

```python
import psutil
import getpass
from .types import ProcessInfo

def _list_processes_psutil(user: str | None) -> list[ProcessInfo]:
    infos: list[ProcessInfo] = []
    for p in psutil.process_iter(attrs=["pid", "username", "cpu_percent", "memory_percent", "cmdline"]):
        try:
            if user is not None and p.info["username"] != user:
                continue
            cmdline = " ".join(p.info.get("cmdline") or [])
            infos.append(ProcessInfo(
                pid=p.info["pid"],
                user=p.info["username"] or "",
                cpu_percent=float(p.info.get("cpu_percent") or 0.0),
                mem_percent=float(p.info.get("memory_percent") or 0.0),
                command=cmdline,
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return infos
```

**ps path (fallback) example command:**

```bash
ps -eo pid,user,%cpu,%mem,command --sort=-%cpu
```

Parse stdout lines ignoring the header row.

**Handler flow:**

1. If `config.features.proc_enabled` is `False`, return MCP error `"FEATURE_DISABLED"`.
2. Get list of `ProcessInfo`.
3. Sort by CPU descending (if not already sorted).
4. `total_processes = len(infos)`.
5. Truncate to `max_results`.
6. Return `processes`, `total_processes`, `truncated`.

---

### 4.3 MCP Tool: `linux.proc_kill`

#### 4.3.1 Purpose

Send a signal to a specific PID with safety checks.

#### 4.3.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "pid": { "type": "integer" },
    "signal": {
      "type": "string",
      "enum": ["TERM", "KILL", "INT", "HUP"],
      "default": "TERM"
    }
  },
  "required": ["pid"]
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

#### 4.3.3 Handler Signature

```python
def mcp_linux_proc_kill(
    pid: int,
    signal: str = "TERM",
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.3.4 Implementation Steps

1. **Feature flag check**
   - If `config.features.proc_enabled` is `False`, return `"FEATURE_DISABLED"`.

2. **Protect critical PIDs**
   - Disallow `pid == 1`.
   - Determine current server PID, e.g.:

```python
import os
MCP_PID = os.getpid()
if pid == MCP_PID:
    # Forbid self-kill.
```

3. **User ownership check (optional but recommended)**
   - If `config.process_limits.allow_kill_other_users` is `False`:
     - Resolve owner of `pid` with `psutil` or `ps`.
     - Compare with current username (`getpass.getuser()`).
     - If mismatch → `"PERMISSION_DENIED"` with clear message.

4. **Map signal string to actual signal**
   - Use `signal.SIGTERM`, `SIGKILL`, etc.

```python
import signal as sigmod

SIGNALS = {
    "TERM": sigmod.SIGTERM,
    "KILL": sigmod.SIGKILL,
    "INT": sigmod.SIGINT,
    "HUP": sigmod.SIGHUP,
}
```

5. **Execute kill**
   - `os.kill(pid, SIGNALS[signal])`.

6. **Return payload**

```python
return {
    "success": True,
    "message": f"Sent SIG{signal} to pid {pid}",
}
```

#### 4.3.5 Errors

- `"PROCESS_NOT_FOUND"`: when pid does not exist.
- `"PERMISSION_DENIED"`: user mismatch, or system policy.
- `"INVALID_ARGUMENT"`: invalid signal name.
- `"KILL_FORBIDDEN"`: PID 1 or MCP_PID.

---

## 5. Detailed Design — System Snapshot Tools (`sysinfo.py`)

### 5.1 Shared Types

**File:** `llmc_mcp/tools/linux_ops/types.py`

```python
from dataclasses import dataclass
from typing import List

@dataclass
class SysDiskInfo:
    mount: str
    used_percent: float

@dataclass
class SysSnapshot:
    cpu_percent: float
    load_avg_1: float
    load_avg_5: float
    load_avg_15: float
    mem_used_mb: int
    mem_total_mb: int
    disks: List[SysDiskInfo]
    short_summary: str
```

### 5.2 MCP Tool: `linux.sys_snapshot`

#### 5.2.1 Purpose

Return a compact snapshot of system resource usage for quick health checks.

#### 5.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {}
}
```

(no arguments required; could be extended later with an `include_disks` flag, etc.)

**Response:**

```json
{
  "type": "object",
  "properties": {
    "cpu_percent": { "type": "number" },
    "load_avg": {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 3,
      "maxItems": 3
    },
    "mem_used_mb": { "type": "integer" },
    "mem_total_mb": { "type": "integer" },
    "disks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "mount": { "type": "string" },
          "used_percent": { "type": "number" }
        },
        "required": ["mount", "used_percent"]
      }
    },
    "short_summary": { "type": "string" }
  },
  "required": [
    "cpu_percent",
    "load_avg",
    "mem_used_mb",
    "mem_total_mb",
    "disks",
    "short_summary"
  ]
}
```

#### 5.2.3 Handler Signature

```python
def mcp_linux_sys_snapshot(
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 5.2.4 Implementation Strategy

Primary path: **psutil**.

1. **CPU and load**

```python
import psutil
import os

cpu_percent = psutil.cpu_percent(interval=0.0)
load1, load5, load15 = os.getloadavg()  # Linux/Unix
```

2. **Memory**

```python
vm = psutil.virtual_memory()
mem_used_mb = int(vm.used / (1024 * 1024))
mem_total_mb = int(vm.total / (1024 * 1024))
```

3. **Disks**

```python
disks = []
for part in psutil.disk_partitions(all=False):
    usage = psutil.disk_usage(part.mountpoint)
    disks.append(SysDiskInfo(
        mount=part.mountpoint,
        used_percent=float(usage.percent),
    ))
```

4. **Summary**

Generate a simple human-readable summary, e.g.:

```python
short_summary = (
    f"CPU {cpu_percent:.0f}%, "
    f"Load {load1:.2f}/{load5:.2f}/{load15:.2f}, "
    f"RAM {mem_used_mb}/{mem_total_mb} MB, "
    f"{disks[0].mount} {disks[0].used_percent:.0f}% used"
)
```

5. **Return**

Convert fields to JSON-serializable primitives and return.

**Fallback (no psutil):**

- Use `uptime` for load,
- `free -m` for memory,
- `df -h` for disks,
- parse outputs via TE shell wrapper.

---

### 5.3 Optional Tools: `linux.sys_services`, `linux.sys_logs`

These are optional and may be gated by `LinuxOpsFeatureFlags.system_enabled` and/or separate toggles.

#### 5.3.1 `linux.sys_services` (Optional)

- Invoke `systemctl list-units --type=service --state=running`.
- Return a list of service names + descriptions, limited to a small number (e.g., 100).
- Use primarily for high-level “what’s running?” context.

#### 5.3.2 `linux.sys_logs` (Optional)

- Invoke `journalctl -n 100 --no-pager` or tail key logs (`/var/log/syslog`, etc.).
- Provide a bounded text snippet, potentially handle-backed if large.
- Should be disabled by default in config due to sensitivity.

---

## 6. Observability & Error Handling

### 6.1 Logging

All L2 handlers log at INFO:

- `linux.proc_list`:
  - `max_results`, `user` filter, `total_processes`, `truncated`.
- `linux.proc_kill`:
  - `pid`, `signal`, result (`success` / failure code).
- `linux.sys_snapshot`:
  - key metrics used in summary.

### 6.2 Metrics

- Increment counters per tool call.
- Histogram latencies per tool.
- For `proc_kill`, count by:
  - success,
  - various error categories (PERMISSION, NOT_FOUND, FORBIDDEN).

---

## 7. Testing Plan

### 7.1 Unit Tests

**File:** `tests/test_linux_ops_proc.py`

Scenarios:

- `proc_list`:
  - With psutil: stub `psutil.process_iter` to return fake processes.
  - With fallback: stub TE shell or `subprocess` to return sample `ps` output.
  - `user` filter applied correctly.
  - Truncation when many processes.
- `proc_kill`:
  - PID 1 → `"KILL_FORBIDDEN"`.
  - MCP PID → `"KILL_FORBIDDEN"`.
  - Other user’s process with `allow_kill_other_users = False` → `"PERMISSION_DENIED"`.
  - Happy path: `os.kill` is called with correct signal.

**File:** `tests/test_linux_ops_sysinfo.py`

- Mock psutil / shell outputs:
  - `cpu_percent`, `getloadavg`, `virtual_memory`, `disk_partitions`, `disk_usage`.
- Validate that snapshot JSON contains expected fields and summary.

### 7.2 Integration Tests

**File:** `tests/integration/test_mcp_linuxops_proc_sys.py`

Tests (non-destructive):

- `linux.proc_list`:
  - Called with small `max_results` (e.g., 10).
  - Returns correct JSON shape.
- `linux.sys_snapshot`:
  - Returns plausible values (non-negative, lists of length 3, etc.).
- `linux.proc_kill`:
  - Use a short-lived test process (e.g., `sleep 30`) started by the test suite:
    - Verify that `proc_kill` successfully terminates it.
    - Confirm process is gone.

---

## 8. Risks and Mitigations

- **Risk:** Aggressive process killing by the model.
  - **Mitigation:** 
    - Feature flag to disable `proc_kill`.
    - Strong defaults (disallow other users’ processes).
    - PIDs 1 and MCP server PID hard-blocked.

- **Risk:** Process listing leaks too much multi-user info.
  - **Mitigation:**
    - Default `user` filter to current user when `allow_kill_other_users = False`.
    - Config flag to permit full system listing only when desired.

- **Risk:** No psutil available leading to brittle parsing.
  - **Mitigation:**
    - Keep shell fallback simple and test against representative output.
    - Prefer psutil install in LLMC environments.

---

## 9. Completion Criteria (Phase L2)

Phase L2 is complete when:

1. `linux.proc_list` and `linux.proc_kill` are implemented and registered.
2. `linux.sys_snapshot` is implemented and registered.
3. Optional `linux.sys_services` / `linux.sys_logs` are implemented or explicitly out-scoped and disabled.
4. All L2 unit tests pass.
5. L2 integration tests pass on a reference Linux dev environment.
6. Config documentation updated to describe process/system flags and safety defaults.

