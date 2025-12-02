# Software Design Document — LLMC MCP LinuxOps Phase L1 (Core FS & Search)

Version: v1.0  
Owner: LLMC  
Status: Draft (Ready for implementation)  
Date: 2025-12-01  

---

## 0. Overview

### 0.1 Purpose

Phase L1 extends the LLMC MCP server with **core Linux file-system and search capabilities** under the `linux.*` tool namespace, matching the Desktop Commander capability surface while:

- Minimizing **prompt/context bloat**.
- Assuming the model already knows **basic Linux tools** (ls, find, rg/grep).
- Routing all real work through **TE wrappers** and **safe FS helpers** instead of direct shell exposure.
- Providing **summary-first** results with optional **handles** for large outputs.

This SDD covers:

- FS tools: `linux.fs_read`, `linux.fs_write`, `linux.fs_list`, `linux.fs_move`, `linux.fs_delete`, `linux.fs_mkdirs`
- Search tools: `linux.search_files`, `linux.search_content`
- Handle store integration for large outputs.

### 0.2 Goals

- Provide a **small, composable** tool surface to allow agents to:
  - Inspect files and directory trees.
  - Create and modify files and folders.
  - Search file names and content efficiently.
- Enforce **safety** via:
  - Root allowlists.
  - Bounded outputs.
  - Handle-based expansion.
- Integrate cleanly with existing:
  - MCP server,
  - TE layer,
  - LLMC config, metrics, and audit logging.

### 0.3 Non-Goals

- No Windows/macOS support.
- No binary file inspection logic beyond raw byte reads.
- No patching (handled in later phase).
- No semantic search (handled by LLMC RAG, not LinuxOps).

---

## 1. Requirements

### 1.1 Functional Requirements

**FS Read**

- R1: Read text files from allowed paths.
- R2: Support line-based slicing (`offset_lines`, `max_lines`).
- R3: If file is larger than the slice, return:
  - a truncated view, and
  - a handle to retrieve full content later.

**FS Write**

- R4: Write or append UTF-8 text to a file.
- R5: Optionally validate existing content using a `expected_sha256` precondition.
- R6: Return bytes written and new SHA-256 hash.

**FS List**

- R7: List entries under a directory with:
  - depth limit,
  - optional glob filtering,
  - optional hidden files.
- R8: Bound result size and provide handle if truncated.

**FS Move/Delete/Mkdirs**

- R9: Move files/directories within allowed roots.
- R10: Delete files/directories with guard rails (no deleting allowed roots themselves).
- R11: Create directories recursively.

**Search Files**

- R12: Search for files by name using pattern + optional glob filter.
- R13: Respect allowed roots and bounds on result size.

**Search Content**

- R14: Search file contents using pattern + optional glob filter.
- R15: Support literal/regex, case sensitivity, and context lines.
- R16: Return structured hits; provide handle for full output if truncated.

### 1.2 Non-Functional Requirements

- **Performance:** Reasonable latency (< 500 ms) for typical directory trees and search operations on medium-sized repos.
- **Token Efficiency:** Default responses should be compact summaries, with explicit handle-based expansion.
- **Safety:** Enforce root allowlist and command allowlists; no path traversal escapes.
- **Observability:** Log all tool invocations with:
  - tool name,
  - duration,
  - error codes,
  - truncated=true/false.

---

## 2. High-Level Design (Phase L1 Slice)

### 2.1 Components

Relevant components (from HLD/LLD):

- `LinuxOpsConfig` (config.py)
- `LinuxOpsRoots` (allowed roots)
- TE Filesystem wrapper (filesystem.py)
- TE Search wrapper (search.py)
- Handle store (handles.py)
- MCP tool handlers (fs.py, search.py)
- MCP server registration (server.py or equivalent)

### 2.2 Data Flow

Example for `linux.search_content`:

1. MCP client calls `linux.search_content` with args.
2. MCP server:
   - Validates auth and tool schema.
   - Calls `mcp_linux_search_content(...)`.
3. `mcp_linux_search_content`:
   - Normalizes and validates `root` using `LinuxOpsConfig`.
   - Calls `te.search.search_content(...)`.
   - Truncates hits if needed and, on overflow, stores full results in handle store.
4. Handler returns compact JSON payload with:
   - summary-level hits,
   - `total_hits`,
   - `truncated`,
   - optional `handle` ID.
5. Agent uses the structured result to decide next actions; can call `linux.handle_read` (Phase L1+X tie-in) if it needs more.

---

## 3. Detailed Design — Config & Cross-Cutting

### 3.1 LinuxOpsConfig (Phase L1 Subset)

**File:** `llmc_mcp/tools/linux_ops/config.py`  

For Phase L1, we only require **roots**; other sections (commands, process limits) can be held for later phases.

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class LinuxOpsRoots:
    allowed_roots: List[str] = field(default_factory=list)
    enforce_roots: bool = True

@dataclass
class LinuxOpsConfig:
    roots: LinuxOpsRoots = field(default_factory=LinuxOpsRoots)
    # Additional fields (commands, process_limits, features) added in later phases
```

**Loading from `llmc.toml`:**

```toml
[mcp.linux_ops.roots]
allowed_roots = ["~/src/llmc", "~"]
enforce_roots = true
```

Config loader (pseudo):

```python
def load_linux_ops_config(toml_cfg: dict) -> LinuxOpsConfig:
    roots_cfg = toml_cfg.get("mcp", {}).get("linux_ops", {}).get("roots", {})
    return LinuxOpsConfig(
        roots=LinuxOpsRoots(
            allowed_roots=roots_cfg.get("allowed_roots", []),
            enforce_roots=roots_cfg.get("enforce_roots", True),
        )
    )
```

**Path normalization helper (core for L1):**

```python
import os
from .errors import InvalidPathError

def normalize_path(path: str, config: LinuxOpsConfig) -> str:
    # Expand user (~) and resolve to absolute path
    expanded = os.path.expanduser(path)
    norm = os.path.abspath(expanded)

    if not config.roots.enforce_roots or not config.roots.allowed_roots:
        return norm

    for root in config.roots.allowed_roots:
        root_expanded = os.path.abspath(os.path.expanduser(root))
        if norm.startswith(root_expanded + os.sep) or norm == root_expanded:
            return norm

    raise InvalidPathError(f"Path '{path}' is outside allowed roots")
```

### 3.2 Handle Store (Phase L1 Usage)

Phase L1 uses handle store for:

- Large `fs_read` results (full file).
- Large `fs_list` results (full entry list).
- Large search results (full hits list).

See LLD for underlying implementation; this SDD only constrains usage patterns:

- Always store **raw payload** (bytes for file content, JSON-encoded bytes for search/file lists).
- Meta should include:
  - `{"kind": "file_content" | "fs_list" | "search_hits", "path": ..., "root": ...}`.
- Caller receives only handle ID, not internal details.

---

## 4. Detailed Design — FS Tools

### 4.1 MCP Tool: `linux.fs_read`

#### 4.1.1 Purpose

Read a text file from a normalized allowed path and return a bounded number of lines plus optional handle for full content.

#### 4.1.2 MCP Schema (Conceptual)

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "offset_lines": { "type": "integer", "minimum": 0, "default": 0 },
    "max_lines": { "type": "integer", "minimum": 1, "maximum": 2000, "default": 200 }
  },
  "required": ["path"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "content": { "type": "string" },
    "handle": { "type": ["string", "null"] },
    "meta": {
      "type": "object",
      "properties": {
        "path": { "type": "string" },
        "total_lines": { "type": "integer" },
        "truncated": { "type": "boolean" }
      },
      "required": ["path", "total_lines", "truncated"]
    }
  },
  "required": ["content", "meta"]
}
```

#### 4.1.3 Handler Signature

```python
def mcp_linux_fs_read(
    path: str,
    offset_lines: int = 0,
    max_lines: int = 200,
    *,
    config: LinuxOpsConfig,
) -> dict:
    ...
```

#### 4.1.4 Implementation Steps

1. **Normalize path**
   - Use `normalize_path(path, config)`.
2. **Read file bytes**
   - Use TE filesystem helper: `data = read_file(npath)`.
   - Max bytes limit can be enforced at `read_file` level (e.g. 5–10 MB) with `OutputTooLargeError` on overflow.
3. **Decode and slice**
   - `text = data.decode("utf-8", errors="replace")`.
   - `lines = text.splitlines()`.
   - Compute slice `[offset_lines : offset_lines + max_lines]`.
4. **Truncation & handle**
   - If `end < total_lines`, mark `truncated = True` and create a handle:
     - `hd = create_handle("file_content", {"path": npath}, data)`.
5. **Return**
   - Payload as defined by schema.

#### 4.1.5 Errors

- `InvalidPathError` → MCP error `"INVALID_PATH"`.
- `FileNotFoundError` → MCP error `"NOT_FOUND"`.
- `PermissionError` → MCP error `"PERMISSION_DENIED"`.
- `OutputTooLargeError` → MCP error `"OUTPUT_TOO_LARGE"`.

---

### 4.2 MCP Tool: `linux.fs_write`

#### 4.2.1 Purpose

Write (rewrite) or append UTF-8 text to a file with optional precondition based on existing hash.

#### 4.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "content": { "type": "string" },
    "mode": { "type": "string", "enum": ["rewrite", "append"], "default": "rewrite" },
    "expected_sha256": { "type": ["string", "null"] }
  },
  "required": ["path", "content"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "bytes_written": { "type": "integer" },
    "new_sha256": { "type": "string" }
  },
  "required": ["bytes_written", "new_sha256"]
}
```

#### 4.2.3 Handler Signature

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

#### 4.2.4 Implementation Steps

1. Normalize path.
2. If `expected_sha256` is provided:
   - Attempt to read existing file:
     - When not found: **fail** with `"SHA_MISMATCH"` to force explicit creation, or allow if we decide new file is acceptable — behavior should be clearly documented; recommended default: mismatch if file exists and hash differs, no check if file missing.
   - Compute hash and compare.
3. Encode `content` to bytes.
4. Depending on `mode`:
   - `"rewrite"`:
     - Write atomically: `path.tmp` then `os.replace`.
   - `"append"`:
     - Open with `ab` and write directly.
5. Compute new SHA-256 over resulting file.
6. Return `bytes_written` and `new_sha256`.

#### 4.2.5 Errors

- `"INVALID_PATH"`, `"PERMISSION_DENIED"`.
- `"SHA_MISMATCH"` when precondition fails.
- `"WRITE_FAILED"` generic.

---

### 4.3 MCP Tool: `linux.fs_list`

#### 4.3.1 Purpose

List contents of a directory tree, bounded by depth and max entries, with optional glob filtering and hidden inclusion.

#### 4.3.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "depth": { "type": "integer", "minimum": 0, "maximum": 10, "default": 2 },
    "include_hidden": { "type": "boolean", "default": false },
    "file_glob": { "type": ["string", "null"] }
  },
  "required": ["path"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "type": { "type": "string" },
          "size_bytes": { "type": "integer" },
          "mtime_iso": { "type": "string" }
        },
        "required": ["path", "type"]
      }
    },
    "truncated": { "type": "boolean" },
    "handle": { "type": ["string", "null"] }
  },
  "required": ["entries", "truncated"]
}
```

#### 4.3.3 Handler Signature

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

#### 4.3.4 Implementation Steps

1. Normalize root path.
2. Validate `depth` is within configured maximum.
3. Use TE filesystem helper `list_dir` or implement:
   - `os.walk` with:
     - depth-limited recursion,
     - hidden file/dir filtering,
     - optional `fnmatch`-style glob.
4. Collect `FileEntry` objects up to `max_entries`.
5. If more entries exist:
   - Set `truncated = True`.
   - Serialize full list as JSON, store in handle.
6. Return entries (possibly limited slice) and handle.

#### 4.3.5 Errors

- `"INVALID_PATH"`, `"NOT_A_DIRECTORY"`.

---

### 4.4 MCP Tools: `linux.fs_move`, `linux.fs_delete`, `linux.fs_mkdirs`

#### 4.4.1 Purpose

Simple wrappers around core filesystem operations with root checking.

#### 4.4.2 Shared Considerations

- All paths must be normalized and validated.
- For moves and deletes, both source and target must fall under allowed roots (if `enforce_roots`).

##### 4.4.3 `linux.fs_move`

**Args:**

```json
{
  "source": "string",
  "target": "string"
}
```

**Behavior:**

- Normalize both.
- Ensure source exists.
- Use `shutil.move(source, target)`.
- Return `{"ok": true, "source": ..., "target": ...}`.

##### 4.4.4 `linux.fs_delete`

**Args:**

```json
{
  "path": "string",
  "recursive": { "type": "boolean", "default": false }
}
```

**Behavior:**

- Normalize path.
- Guard against:
  - deleting allowed roots themselves,
  - deleting `/` or equivalent.
- If directory:
  - `recursive=false` → error `"IS_DIRECTORY"`.
  - `recursive=true` → `shutil.rmtree`.
- If file: `os.remove`.

##### 4.4.5 `linux.fs_mkdirs`

**Args:**

```json
{
  "path": "string",
  "exist_ok": { "type": "boolean", "default": true }
}
```

**Behavior:**

- Normalize path.
- `os.makedirs(path, exist_ok=exist_ok)`.

---

## 5. Detailed Design — Search Tools

### 5.1 MCP Tool: `linux.search_files`

#### 5.1.1 Purpose

Search for files under a root directory using a pattern and optional glob; results are bounded and handle-backed.

#### 5.1.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "root": { "type": "string" },
    "pattern": { "type": "string" },
    "file_glob": { "type": ["string", "null"] },
    "max_results": { "type": "integer", "minimum": 1, "maximum": 2000, "default": 200 }
  },
  "required": ["root", "pattern"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "hits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" }
        },
        "required": ["path"]
      }
    },
    "total_hits": { "type": "integer" },
    "truncated": { "type": "boolean" },
    "handle": { "type": ["string", "null"] }
  },
  "required": ["hits", "total_hits", "truncated"]
}
```

#### 5.1.3 Handler Signature

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

#### 5.1.4 Implementation Steps

1. Normalize `root`.
2. Delegate to TE search wrapper:

```python
paths = te_search.search_files(
    root=root_norm,
    pattern=pattern,
    file_glob=file_glob,
    max_results=max_results + 1,  # overshoot to detect truncation
)
```

3. Determine `total_hits = len(paths)`.
4. If `total_hits > max_results`:
   - `hits = paths[:max_results]`.
   - `truncated = True`.
   - Store full list in handle (JSON).
5. Else:
   - `hits = paths`.
   - `truncated = False`.
6. Return structured payload.

---

### 5.2 MCP Tool: `linux.search_content`

#### 5.2.1 Purpose

Search file contents for a pattern with optional literal/regex mode and case options; return structured snippets.

#### 5.2.2 MCP Schema

**Arguments:**

```json
{
  "type": "object",
  "properties": {
    "root": { "type": "string" },
    "pattern": { "type": "string" },
    "file_glob": { "type": ["string", "null"] },
    "literal": { "type": "boolean", "default": false },
    "ignore_case": { "type": "boolean", "default": true },
    "context_lines": { "type": "integer", "minimum": 0, "maximum": 10, "default": 3 },
    "max_results": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 100 }
  },
  "required": ["root", "pattern"]
}
```

**Response:**

```json
{
  "type": "object",
  "properties": {
    "hits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "line": { "type": "integer" },
          "snippet": { "type": "string" }
        },
        "required": ["path", "line", "snippet"]
      }
    },
    "total_hits": { "type": "integer" },
    "truncated": { "type": "boolean" },
    "handle": { "type": ["string", "null"] }
  },
  "required": ["hits", "total_hits", "truncated"]
}
```

#### 5.2.3 Handler Signature

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

#### 5.2.4 Implementation Steps

1. Normalize `root`.
2. Delegate to TE search:

```python
hits = te_search.search_content(
    root=root_norm,
    pattern=pattern,
    file_glob=file_glob,
    literal=literal,
    ignore_case=ignore_case,
    context_lines=context_lines,
    max_results=max_results + 1,
)
```

3. `total_hits = len(hits)`.
4. If `total_hits > max_results`:
   - `trimmed_hits = hits[:max_results]`.
   - `truncated = True`.
   - Store full hits list as handle (JSON).
5. Else:
   - `trimmed_hits = hits`.
   - `truncated = False`.
6. Convert `SearchHit` objects to dicts and return.

---

## 6. Observability & Error Handling

### 6.1 Logging

Each L1 handler should log at INFO level:

- tool name,
- normalized root/path(s),
- duration,
- truncated flag,
- error codes if any.

Example:

```python
log.info(
    "linux.fs_read completed",
    extra={
        "tool": "linux.fs_read",
        "path": npath,
        "offset_lines": offset_lines,
        "max_lines": max_lines,
        "truncated": truncated,
        "duration_ms": duration_ms,
    },
)
```

### 6.2 Metrics

Integrate with LLMC metrics by emitting:

- increment per tool call,
- latency histogram per tool,
- error counter by error code.

Implementation defers to existing LLMC infra; only requirement is to ensure each handler calls a small shared helper like:

```python
with record_tool_metrics("linux.search_content") as m:
    ...
    m.mark_success()
```

---

## 7. Testing Plan

### 7.1 Unit Tests

**Files:**

- `tests/test_linux_ops_fs.py`
- `tests/test_linux_ops_search.py`

**FS tests:**

- `normalize_path` behavior:
  - inside allowed root,
  - outside allowed root → `InvalidPathError`.
- `fs_read`:
  - small file, no truncation.
  - larger file → truncation + handle.
- `fs_write`:
  - rewrite and append modes.
  - expected_sha256 match and mismatch.
- `fs_list`:
  - depth limits,
  - hidden filtering,
  - glob filtering,
  - truncation behavior.
- `fs_move/delete/mkdirs`:
  - simple success cases,
  - invalid path cases.

**Search tests:**

- `search_files`:
  - pattern match on known tree.
  - result truncation and handle usage (mock handle store).
- `search_content`:
  - literal vs regex,
  - ignore_case true/false,
  - context_lines behavior,
  - truncation.

### 7.2 Integration Tests

**Files:**

- `tests/integration/test_mcp_linuxops_fs_search.py`

Tests:

- Start MCP server with LinuxOps enabled and a temp repo root.
- Invoke each L1 tool via MCP client:
  - Roundtrip JSON validation.
  - Path normalization and safety semantics.
  - Handle presence when results are large (can stub underlying handle store to avoid SQLite if needed).

---

## 8. Risks and Mitigations

- **Risk:** Misconfigured allowed roots could expose more FS than intended.
  - **Mitigation:** Default to strict, empty roots and require explicit config; log allowed roots on startup.
- **Risk:** Unbounded results causing heavy memory usage or large MCP payloads.
  - **Mitigation:** Hard-coded limits (`max_lines`, `max_entries`, `max_results`) plus handle store.
- **Risk:** Path traversal or symlink tricks.
  - **Mitigation:** Use `os.path.abspath` after `expanduser`; treat symlink targets as if they were actual paths (still must match allowed roots).

---

## 9. Completion Criteria (Phase L1)

Phase L1 is complete when:

1. All L1 tool handlers are implemented and registered.
2. All L1 unit tests pass.
3. Integration tests for FS and search MCP tools pass.
4. Basic metrics and logging for L1 tools are wired into LLMC observability.
5. A short doc section is added to `DOCS/mcp_linuxops.md` describing core FS & search tools.

