# Low-Level Design — LLMC MCP LinuxOps (Desktop Commander Parity)

Version: v1.0  
Owner: LLMC  
Status: Draft (post-HLD, pre-implementation)  
Date: 2025-12-01  

---

## 0. Scope and References

This Low-Level Design (LLD) refines the **LLMC MCP LinuxOps HLD** into concrete modules, data structures, function signatures, and task units for agents to implement in phases.

It covers:

- All **LinuxOps MCP tools** (fs, search, patching, processes, REPLs, system snapshot, stats, onboarding macros).
- Cross-cutting components:
  - TE wrappers for shell/fs/search/proc,
  - handle store,
  - process registry,
  - config integration,
  - logging/metrics.
- A small roadmap/checklist for agents to track completion of phases.

Each major unit is annotated with:

- `Complexity`: `S`, `M`, `L` (small/medium/large).
- `ChangeType`: one or more of:
  - `NewFeature`
  - `Refactor`
  - `Config`
  - `Infra`
  - `Docs`
  - `Tests`

Use this LLD as the **single source of truth** for how to wire LinuxOps into the existing MCP server and TE infrastructure.

---

## 1. Conventions

### 1.1 Module Layout (Proposed)

Assuming existing MCP server package `llmc_mcp`:

- `llmc_mcp/`
  - `__init__.py`
  - `server.py` (existing MCP server)
  - `tools/`
    - `__init__.py`
    - `linux_ops/`
      - `__init__.py`
      - `fs.py`
      - `search.py`
      - `patch.py`
      - `proc.py`
      - `sysinfo.py`
      - `stats.py`
      - `onboarding.py`
      - `handles.py`
      - `config.py`
      - `errors.py`
      - `types.py`
  - `te/` (existing or new)
    - `__init__.py`
    - `shell.py`
    - `filesystem.py`
    - `search.py`
    - `process.py`
    - `handles.py`

- `tests/`
  - `test_linux_ops_fs.py`
  - `test_linux_ops_search.py`
  - `test_linux_ops_patch.py`
  - `test_linux_ops_proc.py`
  - `test_linux_ops_sysinfo.py`
  - `test_linux_ops_stats.py`
  - `test_linux_ops_onboarding.py`

- `DOCS/`
  - `mcp_linuxops.md` (short user-facing doc)
  - `mcp_linuxops_tools.md` (tool catalog, machine-friendly)

> **Complexity**: M  
> **ChangeType**: NewFeature, Infra, Docs, Tests  

### 1.2 Coding Conventions

- Language: Python 3.11+.
- Logging: `logging.getLogger(__name__)`.
- Type hints: full `typing` coverage for public functions.
- Exceptions: use custom error types from `errors.py`, convert to MCP error shapes at server boundary.
- File encoding: default UTF-8, with fallback/override allowed via config if needed.

---

## 2. Cross-Cutting Components

### 2.1 LinuxOps Config

**Module**: `llmc_mcp/tools/linux_ops/config.py`

#### Data Model

```python
from dataclasses import dataclass, field
from typing import List, Optional, Set

@dataclass
class LinuxOpsRoots:
    allowed_roots: List[str] = field(default_factory=list)
    # If True, restrict fs operations to allowed_roots only.
    enforce_roots: bool = True

@dataclass
class LinuxOpsCommands:
    allowed_binaries: Set[str] = field(default_factory=set)
    unsafe_binaries: Set[str] = field(default_factory=set)
    allow_unsafe: bool = False

@dataclass
class LinuxOpsProcessLimits:
    max_procs_per_session: int = 4
    max_procs_total: int = 32
    default_timeout_sec: int = 60
    max_timeout_sec: int = 600

@dataclass
class LinuxOpsFeatureFlags:
    fs_enabled: bool = True
    proc_enabled: bool = True
    repl_enabled: bool = True
    system_enabled: bool = True

@dataclass
class LinuxOpsConfig:
    roots: LinuxOpsRoots = field(default_factory=LinuxOpsRoots)
    commands: LinuxOpsCommands = field(default_factory=LinuxOpsCommands)
    process_limits: LinuxOpsProcessLimits = field(default_factory=LinuxOpsProcessLimits)
    features: LinuxOpsFeatureFlags = field(default_factory=LinuxOpsFeatureFlags)
```

Config is populated from `llmc.toml` under section `mcp.linux_ops.*`.

> **Complexity**: S  
> **ChangeType**: NewFeature, Config  

### 2.2 Error Types

**Module**: `llmc_mcp/tools/linux_ops/errors.py`

Define a base error and specific subclasses:

```python
class LinuxOpsError(Exception):
    code: str = "LINUXOPS_ERROR"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code

class InvalidPathError(LinuxOpsError):
    code = "INVALID_PATH"

class PermissionDeniedError(LinuxOpsError):
    code = "PERMISSION_DENIED"

class CommandNotAllowedError(LinuxOpsError):
    code = "COMMAND_NOT_ALLOWED"

class ProcessNotFoundError(LinuxOpsError):
    code = "PROCESS_NOT_FOUND"

class TimeoutError(LinuxOpsError):
    code = "TIMEOUT"

class OutputTooLargeError(LinuxOpsError):
    code = "OUTPUT_TOO_LARGE"
```

Server layer converts these to MCP error payloads with `code` and `message`.

> **Complexity**: S  
> **ChangeType**: NewFeature  

### 2.3 Types

**Module**: `llmc_mcp/tools/linux_ops/types.py`

Define shared typed dicts/dataclasses for tool payloads:

```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class FileEntry:
    path: str
    type: str  # "file" | "dir" | "symlink" | "other"
    size_bytes: int
    mtime_iso: str

@dataclass
class SearchHit:
    path: str
    line: int
    snippet: str

@dataclass
class ProcessInfo:
    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    command: str

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

@dataclass
class ToolCallRecord:
    tool: str
    args_summary: str
    status: str
    duration_ms: int
    timestamp_iso: str
```

> **Complexity**: S  
> **ChangeType**: NewFeature  

### 2.4 Handle Store

**Module**: `llmc_mcp/tools/linux_ops/handles.py` (frontend), `llmc_mcp/te/handles.py` (backend)

#### Storage

Option A (simple, good enough): SQLite file `linuxops_handles.db` under MCP data dir.  
Schema:

```sql
CREATE TABLE IF NOT EXISTS handles (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    meta_json TEXT NOT NULL,
    payload BLOB NOT NULL
);
```

Handle ID format: `H_<type>_<timestamp>_<rand>` (e.g., `H_srch_20251201T180000Z_ab12cd`).

#### API (Python)

```python
from dataclasses import dataclass

@dataclass
class HandleData:
    id: str
    type: str
    created_at_iso: str
    meta: dict
    payload: bytes

def create_handle(type_: str, meta: dict, payload: bytes) -> HandleData: ...
def get_handle(handle_id: str) -> HandleData: ...
def read_handle_slice(handle_id: str, offset: int, limit: int) -> bytes: ...
def delete_handle(handle_id: str) -> None: ...
```

MCP tool `linux.handle_read` will call `read_handle_slice`.

> **Complexity**: M  
> **ChangeType**: NewFeature, Infra  

### 2.5 TE Shell Wrapper

**Module**: `llmc_mcp/te/shell.py`

Responsibilities:

- Build safe command line (list of strings, no `shell=True`).
- Enforce allowed binaries (from `LinuxOpsConfig.commands`).
- Run with timeout, capture stdout/stderr/exit code.

API:

```python
from dataclasses import dataclass
from typing import Sequence, Mapping, Optional

@dataclass
class ShellResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int

def run_command(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout_sec: int = 60,
    text: bool = True,
) -> ShellResult:
    ...
```

Implementation uses `subprocess.Popen` with `communicate`, or `asyncio` if needed later.

> **Complexity**: M  
> **ChangeType**: NewFeature, Infra  

### 2.6 TE Filesystem Wrapper

**Module**: `llmc_mcp/te/filesystem.py`

Responsibilities:

- Path normalization against allowed roots.
- Read/write/list using Python stdlib.
- Return structured metadata.

Key functions:

```python
def normalize_path(path: str, config: LinuxOpsConfig) -> str: ...
def read_file(path: str, max_bytes: int | None = None) -> bytes: ...
def write_file(path: str, data: bytes, *, rewrite: bool) -> None: ...
def list_dir(path: str, depth: int, include_hidden: bool) -> list[FileEntry]: ...
```

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 2.7 TE Search Wrapper

**Module**: `llmc_mcp/te/search.py`

Responsibilities:

- Call `rg` or `grep` for content.
- Call `fd` or `find` for file names.
- Parse output into `SearchHit` / path lists.

Key functions:

```python
def search_files(
    root: str,
    pattern: str,
    file_glob: str | None,
    max_results: int,
) -> list[str]:
    ...

def search_content(
    root: str,
    pattern: str,
    file_glob: str | None,
    literal: bool,
    ignore_case: bool,
    context_lines: int,
    max_results: int,
) -> list[SearchHit]:
    ...
```

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 2.8 TE Process Wrapper and Registry

**Module**: `llmc_mcp/te/process.py`

Responsibilities:

- Start long-lived processes (REPLs).
- Maintain in-memory registry, optionally backed by a local file or DB.

Registry entry:

```python
from dataclasses import dataclass

@dataclass
class ManagedProcess:
    proc_id: str
    pid: int
    command: str
    cwd: str
    start_time_iso: str
    last_activity_iso: str
    # actual process handle (not serialized)
    p: "subprocess.Popen[str]"
```

API:

```python
def start_process(command: str, cwd: str | None, env: dict | None) -> ManagedProcess: ...
def send_input(proc_id: str, data: str) -> None: ...
def read_output(proc_id: str, timeout_sec: int) -> str: ...
def stop_process(proc_id: str, signal_name: str = "TERM") -> None: ...
def list_processes() -> list[ManagedProcess]: ...
```

> **Complexity**: L  
> **ChangeType**: NewFeature, Infra  

---

## 3. LinuxOps MCP Tool Implementations

Each MCP tool is implemented as a function in `linux_ops/*.py` and registered in `llmc_mcp/server.py` (or equivalent registry) under a `linux.*` namespace.

### 3.1 File Tools — `fs.py`

#### 3.1.1 linux.fs_read

```python
def mcp_linux_fs_read(
    path: str,
    offset_lines: int = 0,
    max_lines: int = 200,
    *,
    config: LinuxOpsConfig,
) -> dict:
    '''Read a text file from a normalized, allowed path and return a bounded number of lines.'''
    # 1. Normalize + validate path.
    npath = normalize_path(path, config)
    # 2. Read file content as bytes, decode UTF-8 with errors='replace'.
    data = read_file(npath)
    text = data.decode("utf-8", errors="replace")
    # 3. Split into lines.
    lines = text.splitlines()
    total_lines = len(lines)
    end = min(total_lines, offset_lines + max_lines)
    chunk = "\n".join(lines[offset_lines:end])
    truncated = end < total_lines
    # 4. If truncated, store full content in handle store.
    handle_id = None
    if truncated:
        hd = create_handle(
            type_="file_content",
            meta={"path": npath},
            payload=data,
        )
        handle_id = hd.id
    # 5. Return MCP payload.
    return {
        "content": chunk,
        "handle": handle_id,
        "meta": {
            "path": npath,
            "total_lines": total_lines,
            "truncated": truncated,
        },
    }
```

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.1.2 linux.fs_write

```python
def mcp_linux_fs_write(
    path: str,
    content: str,
    mode: str = "rewrite",
    expected_sha256: str | None = None,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Implementation details:

1. Normalize path.
2. If `expected_sha256` given:
   - read current file (if exists),
   - verify hash (mismatch → `LinuxOpsError` with code `"SHA_MISMATCH"`).
3. Encode `content` as UTF-8.
4. Write:
   - `rewrite`: open with `wb`.
   - `append`: open with `ab`.
5. Compute new hash.
6. Return `{"bytes_written": n, "new_sha256": hash}`.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.1.3 linux.fs_list

```python
def mcp_linux_fs_list(
    path: str,
    depth: int = 2,
    include_hidden: bool = False,
    file_glob: str | None = None,
    *,
    config: LinuxOpsConfig,
    max_entries: int = 500,
) -> dict:
    ...
```

Implementation:

1. Normalize root.
2. Walk with bounded depth using `os.walk`.
3. Apply `include_hidden` and optional glob filter.
4. Build `FileEntry` objects up to `max_entries`.
5. If exceeded, set `truncated=True` and possibly store full list in a handle.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.1.4 linux.fs_move / fs_delete / fs_mkdirs

Implement as thin wrappers around TE filesystem helpers:

- `fs_move`: `shutil.move`.
- `fs_delete`: `os.remove` or `shutil.rmtree` for directories; guard against deleting allowed root itself.
- `fs_mkdirs`: `os.makedirs(exist_ok=True)`.

> **Complexity**: S  
> **ChangeType**: NewFeature  

### 3.2 Search Tools — `search.py`

#### 3.2.1 linux.search_files

```python
def mcp_linux_search_files(
    root: str,
    pattern: str,
    file_glob: str | None = None,
    max_results: int = 200,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Normalize root.
2. Call `te.search.search_files`.
3. If > `max_results`, truncate and set a handle with full list.
4. Return:
   - `hits: [{"path": ...}, ...]`,
   - `total_hits`,
   - `truncated`,
   - `handle`.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.2.2 linux.search_content

```python
def mcp_linux_search_content(
    root: str,
    pattern: str,
    file_glob: str | None = None,
    literal: bool = False,
    ignore_case: bool = True,
    context_lines: int = 3,
    max_results: int = 100,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Normalize root.
2. Call `te.search.search_content`, obtain list of `SearchHit`.
3. If > `max_results`, truncate and store raw hits in handle.
4. Return structured payload.

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 3.3 Patching Tools — `patch.py`

#### 3.3.1 linux.fs_patch_block

```python
def mcp_linux_fs_patch_block(
    path: str,
    old_text: str,
    new_text: str,
    expected_replacements: int = 1,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Implementation:

1. Normalize path.
2. Read full file content (bounded by size, e.g. max 2 MB; else fail with `OutputTooLargeError`).
3. Count occurrences of `old_text`.
4. If `expected_replacements` != count → error `PATCH_COUNT_MISMATCH`.
5. Replace occurrences.
6. Write back atomically:
   - write to `path + ".tmp"` then `os.replace`.
7. Return:
   - `{"replacements_made": count, "before_snippet": ..., "after_snippet": ...}` where snippets show first occurrence context.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.3.2 linux.fs_apply_diff

```python
def mcp_linux_fs_apply_diff(
    diff_text: str,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Implementation options:

- Use Python `difflib` or shell `patch` command.
- For safety:
  1. Parse diff and ensure all files are under allowed roots.
  2. For each file, create backup `*.bak`.
  3. Apply diff.
  4. On failure, attempt rollback.

Return summary:

```json
{
  "files_modified": ["..."],
  "backups_created": true,
  "message": "Applied diff to 3 files"
}
```

> **Complexity**: L  
> **ChangeType**: NewFeature, Infra  

### 3.4 Process Tools — `proc.py`

#### 3.4.1 linux.proc_list

```python
def mcp_linux_proc_list(
    *,
    config: LinuxOpsConfig,
    max_results: int = 200,
) -> dict:
    ...
```

Implementation:

1. Use `ps -eo pid,user,%cpu,%mem,command --sort=-%cpu`.
2. Parse lines, convert to `ProcessInfo` objects.
3. Truncate to `max_results`, store handle if needed.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.4.2 linux.proc_kill

```python
def mcp_linux_proc_kill(
    pid: int,
    signal: str = "TERM",
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Safety checks:

1. Disallow PID 1 and MCP server PID.
2. Optionally disallow killing processes of other users unless flag set.
3. Use `os.kill(pid, signal)`.

Return payload:

```json
{
  "success": true,
  "message": "Sent SIGTERM to pid 1234"
}
```

> **Complexity**: S  
> **ChangeType**: NewFeature  

#### 3.4.3 linux.proc_tree (optional)

If needed, spawn `ps` or `pstree` to build a simple parent-child mapping.

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 3.5 Interactive Process / REPL Tools — `proc.py`

#### 3.5.1 linux.proc_start

```python
def mcp_linux_proc_start(
    command: str,
    cwd: str | None = None,
    env: dict | None = None,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Validate `config.features.repl_enabled`.
2. Split `command` (e.g. `shlex.split`).
3. Enforce binary allowlist.
4. Use `te.process.start_process`.
5. Immediately read from stdout with small timeout (e.g. 1–2 sec).
6. Register `ManagedProcess` in registry.
7. Return `{"proc_id": ..., "pid": ..., "first_output": ..., "state": "running" | "exited"}`.

> **Complexity**: L  
> **ChangeType**: NewFeature, Infra  

#### 3.5.2 linux.proc_send

```python
def mcp_linux_proc_send(
    proc_id: str,
    input: str,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Lookup `ManagedProcess`.
2. Write `input + "\n"` to stdin.
3. Return `{"acknowledged": true}` if successful.

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.5.3 linux.proc_read

```python
def mcp_linux_proc_read(
    proc_id: str,
    timeout_ms: int = 1000,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Lookup `ManagedProcess`.
2. Use non-blocking read with timeout (poll/select).
3. Return:
   - `{"output": "...", "state": "running" | "exited" | "no_such_process"}`.

> **Complexity**: L  
> **ChangeType**: NewFeature, Infra  

#### 3.5.4 linux.proc_stop

```python
def mcp_linux_proc_stop(
    proc_id: str,
    signal: str = "TERM",
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Flow:

1. Lookup `ManagedProcess`.
2. Send signal; optionally escalate to `KILL` after timeout.
3. Remove from registry.

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 3.6 System Snapshot Tools — `sysinfo.py`

#### 3.6.1 linux.sys_snapshot

```python
def mcp_linux_sys_snapshot(
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Implementation options:

- Use `psutil` if available, else shell commands:
  - `uptime`, `df -h`, `free -m`.
- Aggregate into `SysSnapshot`.

Return:

```json
{
  "cpu_percent": 12.5,
  "load_avg": [0.42, 0.38, 0.35],
  "mem_used_mb": 4096,
  "mem_total_mb": 16384,
  "disks": [{ "mount": "/", "used_percent": 58.0 }],
  "short_summary": "CPU 12%, RAM 4/16 GB, / 58% used"
}
```

> **Complexity**: M  
> **ChangeType**: NewFeature  

#### 3.6.2 linux.sys_services / linux.sys_logs (optional)

- `sys_services`: call `systemctl list-units --type=service --state=running`.
- `sys_logs`: call `journalctl` or tail of log files with bounding.

> **Complexity**: M  
> **ChangeType**: NewFeature  

### 3.7 Stats Tools — `stats.py`

#### 3.7.1 linux.mcp_usage_stats

```python
def mcp_linux_mcp_usage_stats() -> dict:
    ...
```

Implementation:

- Read from existing LLMC metrics or token audit log.
- Aggregate counts and p95 latencies per tool.

Return:

```json
{
  "tools": {
    "linux.fs_read": {"count": 120, "p95_ms": 40},
    "linux.search_content": {"count": 30, "p95_ms": 150},
    ...
  }
}
```

> **Complexity**: M  
> **ChangeType**: NewFeature, Infra  

#### 3.7.2 linux.mcp_recent_calls

```python
def mcp_linux_mcp_recent_calls(
    max_results: int = 50,
    tool_name: str | None = None,
) -> dict:
    ...
```

Implementation:

- Query token audit / structured log store in reverse chronological order.
- Map records to `ToolCallRecord`.

> **Complexity**: M  
> **ChangeType**: NewFeature, Infra  

### 3.8 Onboarding Macros — `onboarding.py`

#### 3.8.1 linux.mcp_run_onboarding

```python
def mcp_linux_mcp_run_onboarding(
    flow_name: str,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

Onboarding flows are just named Python functions:

```python
def onboarding_organize_downloads(config: LinuxOpsConfig) -> dict: ...
def onboarding_explain_repo(config: LinuxOpsConfig) -> dict: ...
def onboarding_system_health(config: LinuxOpsConfig) -> dict: ...
```

Dispatcher:

```python
_ONBOARDING_FLOWS = {
    "organize_downloads": onboarding_organize_downloads,
    "explain_repo": onboarding_explain_repo,
    "system_health": onboarding_system_health,
}
```

Each flow uses LinuxOps tools/TE wrappers internally and returns a short report:

```json
{
  "flow": "organize_downloads",
  "steps": [
    {"description": "Scanned ~/Downloads", "result": "123 files found"},
    {"description": "Proposed folder structure", "result": "docs, images, archives"},
    {"description": "Moved files", "result": "110 files moved"}
  ],
  "summary": "Downloads folder organized into 3 categories."
}
```

> **Complexity**: M  
> **ChangeType**: NewFeature  

---

## 4. MCP Tool Registration

**File**: `llmc_mcp/server.py` (or `tools/__init__.py` depending on current structure)

Add registration entries (example pseudocode):

```python
from llmc_mcp.tools.linux_ops import fs, search, patch, proc, sysinfo, stats, onboarding

LINUXOPS_TOOLS = {
    "linux.fs_read": fs.mcp_linux_fs_read,
    "linux.fs_write": fs.mcp_linux_fs_write,
    "linux.fs_list": fs.mcp_linux_fs_list,
    "linux.fs_move": fs.mcp_linux_fs_move,
    "linux.fs_delete": fs.mcp_linux_fs_delete,
    "linux.fs_mkdirs": fs.mcp_linux_fs_mkdirs,
    "linux.search_files": search.mcp_linux_search_files,
    "linux.search_content": search.mcp_linux_search_content,
    "linux.fs_patch_block": patch.mcp_linux_fs_patch_block,
    "linux.fs_apply_diff": patch.mcp_linux_fs_apply_diff,
    "linux.proc_list": proc.mcp_linux_proc_list,
    "linux.proc_kill": proc.mcp_linux_proc_kill,
    "linux.proc_start": proc.mcp_linux_proc_start,
    "linux.proc_send": proc.mcp_linux_proc_send,
    "linux.proc_read": proc.mcp_linux_proc_read,
    "linux.proc_stop": proc.mcp_linux_proc_stop,
    "linux.sys_snapshot": sysinfo.mcp_linux_sys_snapshot,
    "linux.mcp_usage_stats": stats.mcp_linux_mcp_usage_stats,
    "linux.mcp_recent_calls": stats.mcp_linux_mcp_recent_calls,
    "linux.mcp_run_onboarding": onboarding.mcp_linux_mcp_run_onboarding,
}
```

Tool schemas (argument/return JSON definitions) are defined in MCP’s tool metadata layer and should be kept short (one-line descriptions, minimal examples).

> **Complexity**: M  
> **ChangeType**: NewFeature, Refactor  

---

## 5. Testing Strategy

### 5.1 Unit Tests

Per-module unit tests:

- `test_linux_ops_fs.py`
  - path normalization, fs_read/write/list/move/delete/mkdirs.
  - patch_block happy path and mismatch cases.
- `test_linux_ops_search.py`
  - search_files/content (mock TE search helper if needed).
- `test_linux_ops_proc.py`
  - proc_list parsing of sample `ps` output.
  - proc_kill safety checks.
  - REPL lifecycle with mocked process.
- `test_linux_ops_sysinfo.py`
  - sys_snapshot with stubbed psutil/shell outputs.
- `test_linux_ops_stats.py`
  - usage_stats/recent_calls with stubbed audit store.
- `test_linux_ops_onboarding.py`
  - flows run and produce steps/summary.

> **Complexity**: L  
> **ChangeType**: Tests  

### 5.2 Integration Tests

MCP-level tests that:

- Start MCP server with LinuxOps enabled.
- Call tools via MCP client.
- Assert shapes and core behavior:
  - read/write/list/search on a temp directory tree.
  - proc_list and proc_kill on harmless processes.
  - proc_start/send/read with a simple Python REPL.
  - sys_snapshot returns expected fields.
  - onboarding flows produce structured steps.

> **Complexity**: L  
> **ChangeType**: Tests, Infra  

---

## 6. Agent Roadmap & Checklist

This section is meant to be edited by agents as phases complete. Treat it like a living mini-roadmap.

### 6.1 Phase Overview

- **Phase L1 — Core FS & Search**
  - FS tools (`fs_read/write/list/move/delete/mkdirs`)
  - Search tools (`search_files`, `search_content`)
  - Handle store integration for large results
- **Phase L2 — Process & System Snapshot**
  - `proc_list`, `proc_kill`
  - `sys_snapshot` (+ optional services/logs)
- **Phase L3 — Interactive Processes / REPLs**
  - `proc_start/send/read/stop`
  - Process registry and limits
- **Phase L4 — Stats & Onboarding**
  - `mcp_usage_stats`, `mcp_recent_calls`
  - `mcp_run_onboarding` + 2–3 flows

### 6.2 Implementation Checklist (for Agents)

Use `Status` as one of: `TODO`, `IN_PROGRESS`, `DONE`.

#### Phase L1 — Core FS & Search

| Item ID | Task | Module(s) | Complexity | ChangeType | Status | Notes |
|--------|------|-----------|-----------|------------|--------|-------|
| L1-1 | Implement LinuxOpsConfig and load from `llmc.toml` | linux_ops.config | S | NewFeature, Config | TODO |  |
| L1-2 | Implement TE filesystem wrapper | te.filesystem | M | NewFeature | TODO |  |
| L1-3 | Implement linux.fs_read/write/list/move/delete/mkdirs | linux_ops.fs | M | NewFeature | TODO |  |
| L1-4 | Implement TE search wrapper | te.search | M | NewFeature | TODO |  |
| L1-5 | Implement linux.search_files/search_content | linux_ops.search | M | NewFeature | TODO |  |
| L1-6 | Implement handle store | linux_ops.handles, te.handles | M | NewFeature, Infra | TODO |  |
| L1-7 | Unit tests for FS & search | tests/*fs*, *search* | M | Tests | TODO |  |
| L1-8 | Integration tests for FS & search MCP tools | tests/integration | M | Tests | TODO |  |

#### Phase L2 — Process & System Snapshot

| Item ID | Task | Module(s) | Complexity | ChangeType | Status | Notes |
|--------|------|-----------|-----------|------------|--------|-------|
| L2-1 | Implement ps-based proc_list | linux_ops.proc | M | NewFeature | TODO |  |
| L2-2 | Implement proc_kill with safety checks | linux_ops.proc | S | NewFeature | TODO |  |
| L2-3 | Implement sys_snapshot | linux_ops.sysinfo | M | NewFeature | TODO |  |
| L2-4 | Unit tests for proc_list/kill & sys_snapshot | tests/*proc*, *sysinfo* | M | Tests | TODO |  |
| L2-5 | Integration tests for proc & sys tools | tests/integration | M | Tests | TODO |  |

#### Phase L3 — Interactive Processes / REPLs

| Item ID | Task | Module(s) | Complexity | ChangeType | Status | Notes |
|--------|------|-----------|-----------|------------|--------|-------|
| L3-1 | Implement TE process wrapper & registry | te.process | L | NewFeature, Infra | TODO |  |
| L3-2 | Implement linux.proc_start | linux_ops.proc | L | NewFeature | TODO |  |
| L3-3 | Implement linux.proc_send/read/stop | linux_ops.proc | L | NewFeature | TODO |  |
| L3-4 | Unit tests for REPL lifecycle | tests/*proc* | L | Tests | TODO |  |
| L3-5 | Integration tests for REPL tools | tests/integration | L | Tests | TODO |  |

#### Phase L4 — Stats & Onboarding

| Item ID | Task | Module(s) | Complexity | ChangeType | Status | Notes |
|--------|------|-----------|-----------|------------|--------|-------|
| L4-1 | Implement tool usage aggregation | linux_ops.stats | M | NewFeature, Infra | TODO |  |
| L4-2 | Implement recent MCP call listing | linux_ops.stats | M | NewFeature, Infra | TODO |  |
| L4-3 | Implement onboarding flows dispatcher | linux_ops.onboarding | M | NewFeature | TODO |  |
| L4-4 | Implement core onboarding flows (Downloads, Repo, System Health) | linux_ops.onboarding | M | NewFeature | TODO |  |
| L4-5 | Unit tests for stats & onboarding | tests/*stats*, *onboarding* | M | Tests | TODO |  |
| L4-6 | Integration tests for stats & onboarding | tests/integration | M | Tests | TODO |  |

#### Phase X — Registration, Docs, and Polish (Cross-Phase)

| Item ID | Task | Module(s) | Complexity | ChangeType | Status | Notes |
|--------|------|-----------|-----------|------------|--------|-------|
| X-1 | Register LinuxOps tools in MCP server | server.py | S | NewFeature, Refactor | TODO |  |
| X-2 | Write `DOCS/mcp_linuxops.md` quickstart | DOCS | M | Docs | TODO |  |
| X-3 | Write machine-friendly `DOCS/mcp_linuxops_tools.md` | DOCS | M | Docs | TODO |  |
| X-4 | Wire LinuxOps tools into metrics/audit pipeline | linux_ops.stats | M | Infra | TODO |  |
| X-5 | Add config reference section for LinuxOps in existing config docs | DOCS | S | Docs | TODO |  |

Agents can update `Status` and `Notes` as they complete tasks.  

---

End of LLD.
