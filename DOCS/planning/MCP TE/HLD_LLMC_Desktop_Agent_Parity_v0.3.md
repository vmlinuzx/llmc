# High-Level Design - LLMC Desktop Agent Parity (Linux)

Version: v0.3  
Date: 2025-12-01  
Owner: LLMC

## 1. Problem and goals

LLMC currently exposes a small MCP tool surface (health, RAG search, safe file read, list dir, stat, run cmd). Desktop Commander on the other hand gives Claude a rich, opinionated desktop environment: configuration management, file system navigation, project search, long running processes, and telemetry.

The goal of this design is to let an agent do everything through LLMC that it can do today through Desktop Commander on Linux, while keeping LLMC's constraints:

- Token efficient: do not bloat prompts with huge MCP schemas.  
- Local first: prefer LLMC and TE tooling on the local machine.  
- Safe by default: strict allowlists and directory constraints.  
- Incremental: ship in small phases on top of the existing MCP MVP.  
- Multi-agent capable: support additional agents beyond Claude Desktop over time, with clean per-agent isolation.  
- TE-agnostic: **TE must not know which agent is calling it**; any agent identity stays inside LLMC.

The output of this HLD is the target architecture and capability map; the SDDs and patches will follow.

## 2. Background

### 2.1 LLMC MCP MVP (RAG-first)

The existing MCP MVP HLD and implementation provide:

- HTTP based MCP core with simple tools (read_file, list_dir, stat, run_cmd).  
- RAG adapter to expose LLMC graph search.  
- Config driven behavior via llmc.toml.  
- Basic observability.

This design builds on that work and extends the tool surface to cover Desktop Commander style capabilities, but without reverting to the "30 tools plus huge schemas in every prompt" anti pattern.

### 2.2 Desktop Commander capabilities (Linux)

From the Desktop Commander context documentation, the main capabilities are:

1. Configuration management  
   - get_config  
   - set_config_value  

2. File and directory operations  
   - read_file  
   - read_multiple_files  
   - write_file  
   - create_directory  
   - list_directory  
   - move_file  
   - get_file_info  

3. Search  
   - start_search  
   - get_more_search_results  
   - stop_search  
   - list_searches  

4. Process and session management  
   - start_process  
   - read_process_output  
   - interact_with_process  
   - force_terminate  
   - list_sessions  
   - list_processes  
   - kill_process  

5. Content editing and patching  
   - edit_block (structured edits inside files)

6. Telemetry and introspection  
   - get_usage_stats  
   - get_recent_tool_calls  
   - give_feedback_to_desktop_commander  

7. Prompt and guidance  
   - get_prompts plus rich inline guidance in the context doc.  

LLMC needs to expose equivalent capabilities, but mapped to its own primitives (RAG, TE, metrics) and configuration model.

### 2.3 TE (Tool Envelope) and enrichment patterns

The MCP Server Architecture and TE docs establish the following principles:

- Tools are dumb, LLMC is smart.  
- TE wrappers enrich, rank, and truncate heavy outputs before the model sees them.  
- For large results, TE may return a short header plus a handle; the agent can page or fetch more via follow up calls.  
- Telemetry is logged to a local SQLite database and to LLMC metrics.

Critically for this design:

- **TE is agent-agnostic.** It does not know which LLMC agent (Claude Desktop, other MCP client, LLMC-native agent) is invoking it.  
- At most, TE sees opaque call IDs or session IDs that LLMC can use for correlation, but no stable `agent_id` or model identity.

We will reuse TE patterns for desktop parity (especially for search and large command output), but all **agent identity and policy stay inside LLMC**.

### 2.4 Agent landscape

- **Initial test agent:** Claude via Desktop Commander on Linux, speaking MCP HTTP/stdio to LLMC.  
- **Future agents:** additional LLMC agents (for example TE-integrated CLI agents, other MCP clients, or LLMC-native planners) should be able to reuse the same desktop tool surface.

The design must therefore:

- Track an `agent_id` in LLMC for all desktop tool calls.  
- Enforce **no process sharing between agents** at the LLMC layer. A process session belongs to the agent that created it.  
- Keep TE blind to agent identity (it just sees a generic call/session id).  
- Allow per-agent policy overrides in the future without redesigning the core.

## 3. Scope

### 3.1 In scope

- Linux desktop usage with LLMC running on the same host as the files and processes being managed.  
- Functional parity with Desktop Commander for the capabilities listed in 2.2.  
- Integration with the existing MCP HTTP core and llmc_mcp server.  
- Integration with TE for command execution, search, and result enrichment, **without exposing agent identity to TE**.  
- Security model based on allowed roots and allowlisted commands.  
- Per-agent isolation for process sessions and LLMC-managed process artifacts.  
- Automatic deletion of LLMC-managed process artifact files older than 24 hours.  
- Observability through LLMC metrics, TE telemetry, and JSON logs.

### 3.2 Out of scope (for this HLD)

- Windows and macOS specific behaviors.  
- Remote multi host orchestration beyond what LLMC already does.  
- Advanced agent planning hierarchies (this document assumes an agent already exists).  
- UI work beyond "tools available to an agent".

## 4. Architecture overview

### 4.1 Components

1. **LLMC Core**  
   - Existing orchestrator, router, and RAG graph.  
   - Chooses models, manages sessions, injects context.

2. **Desktop Agent Profile**  
   - An agent configuration in AGENTS.md (and sidecar) that is allowed to use the desktop tool bundle.  
   - Holds instructions about when to use file tools, when to call RAG, and when to prefer TE summarized output.  
   - Identified by `agent_id` (for example `claude_desktop` for the initial Desktop Commander agent).  
   - Designed so that multiple agents can be granted desktop access over time, each with its own policy view if needed.

3. **MCP Desktop Tool Layer (`llmc_mcp.desktop`)**  
   - New logical layer inside `llmc_mcp.server` that exposes a small number of high level tools:  
     - `desktop_fs`  
     - `desktop_search`  
     - `desktop_process`  
     - `desktop_config`  
     - `desktop_telemetry`  
   - Each high level tool is a "tool family" that multiplexes several related actions instead of exposing dozens of separate tools.  
   - Passes `agent_id` and `session_id` into the adapter layer.

4. **TE Execution and Enrichment (`llmc.te`)**  
   - Existing TE CLI and library, callable as a library or via a local subprocess.  
   - Provides enriched execution for commands like grep, find, cat, and generic subprocess runs.  
   - Maintains its own telemetry database and handle-based large result store.  
   - **Does not receive `agent_id` or model identity.** At most, TE sees an opaque `te_call_id` or `te_session_id` that LLMC can correlate in logs if needed.

5. **Desktop Adapter Library (`llmc.desktop.adapter`)**  
   - A thin Python module that implements the Desktop Commander capabilities using:  
     - `fs.py` for safe file system access.  
     - TE for search and heavy CLI commands (agent-agnostic).  
     - Direct `subprocess.Popen` for LLMC-managed long running processes.  
     - A **per-agent, in-memory registry** for long running processes and search sessions.  
   - Enforces **no process sharing**: an agent can only see and control processes it created.  
   - Writes LLMC-managed process artifacts (logs, snapshots) to per-agent directories under LLMC control.  
   - Returns TE style envelopes (summary plus handle) and LLMC envelopes for process output to MCP.

6. **Config and Policy Store**  
   - Section in `llmc.toml` for desktop agent configuration (allowed roots, allowed commands, limits, defaults).  
   - Runtime view exposed via `desktop_config`.  
   - Future-ready structure to allow per-agent overrides (for example keyed by `agent_id`) while keeping a global default.

7. **Observability and Cleanup**  
   - Uses `llmc_mcp.observability` plus TE telemetry to log:  
     - tool name, action, path, command  
     - `agent_id`, `session_id` (LLMC logs only)  
     - durations, bytes read or written  
     - token estimates for enriched results  
   - Runs a lightweight background cleanup job in LLMC that deletes any **LLMC-managed process artifact files** older than 24 hours.

### 4.2 Deployment topology

The default topology for Linux desktop parity:

- LLMC core plus `llmc_mcp` run in one container or process on the desktop.  
- TE runs in-process as a library or via local subprocess (for now, no separate TE daemon).  
- MCP is exposed via HTTP/stdio to Claude Desktop and other MCP clients.

This keeps the internals simple: MCP calls directly into the Desktop Adapter Library, which calls TE (agent-agnostic) and fs helpers.

### 4.3 Logical flows

#### 4.3.1 File operations (`desktop_fs`)

Example: agent wants to read and then edit a config file.

1. Agent calls MCP tool `desktop_fs` with `action="read_file"` and `path`.  
2. MCP Desktop Tool Layer validates the request against config: allowed roots, max size, and captures `agent_id`.  
3. Desktop Adapter uses `fs.read_file` to read from disk and adds metadata (encoding, size, mtime).  
4. For small files, content is returned inline. For large files, an envelope is returned:  
   - summary of the file (first N lines plus stats)  
   - handle that can be passed to `desktop_fs` with `action="read_more"` for paging.  
   - For file paging we can either:  
     - use TE handles (TE still sees no agent identity), or  
     - use LLMC's own handle store under `.llmc/desktop/handles/`.  
5. If the agent later wants to edit a region, it calls `desktop_fs` with `action="edit_block"` and a patch spec.  
6. Desktop Adapter uses a safe edit routine (similar to Desktop Commander `edit_block`) and writes back to disk.  
7. If edit backups are enabled, the previous version is written to a per-agent process artifact directory (for example `.llmc/desktop/process/<agent_id>/<session>/<timestamp>.bak`). These files are subject to the 24h cleanup policy.

#### 4.3.2 Search (`desktop_search`)

Example: agent wants to find usages of a symbol across a repo.

1. Agent calls `desktop_search` with `action="start_search"`, query, root, and optional path filters.  
2. Desktop Adapter invokes TE enriched search (grep or ripgrep wrapper) which:  
   - runs ripgrep with appropriate arguments  
   - ranks results and truncates to a small header list  
   - stores full results under a **TE-managed handle** (`te_handle_id`).  
3. MCP returns an envelope with a ranked result summary and handle (TE handle or LLMC handle).  
4. Agent can call `desktop_search` with `action="get_more"` and the handle to get more results or specific file slices.  
5. `stop_search` or natural expiry cleans up LLMC's in-memory search sessions; TE's own handle retention is governed by TE.  
6. LLMC does **not** need TE to know the agent; per-agent behavior is enforced by LLMC's own search session registry.

#### 4.3.3 Process management (`desktop_process`)

Example: agent starts a test run and watches output.

1. Agent calls `desktop_process` with `action="start_process"`, command, args, and working directory.  
2. Desktop Adapter validates command against allowlist and blocked commands, then spawns a subprocess under a managed session id and **agent-scoped process id** using `subprocess.Popen` directly (not TE).  
3. Initial output is captured and summarized into an LLMC envelope (summary plus handle). On-disk logs or buffers are written to:  
   - `.llmc/desktop/process/<agent_id>/<session_id>/<process_id>/...`  
4. Agent can call:  
   - `action="read_output"` with process id and optional cursor.  
   - `action="send_input"` for interactive sessions (stdin lines).  
   - `action="force_terminate"` or `action="kill"` to stop.  
   - `action="list_processes"` or `action="list_sessions"` to inspect **only its own** active processes and sessions.  
5. Long running processes are tracked in a **per-agent process registry** with timeouts and hard caps on output volume.  
6. A periodic cleanup job in LLMC:  
   - Reaps zombie or stale processes that exceeded configured lifetimes.  
   - Deletes any LLMC-managed process logs and artifacts older than 24 hours. TE's own internal caches are not touched.

#### 4.3.4 Configuration and telemetry

- `desktop_config` provides `get_config` and `set_config_value` operations for the desktop agent config namespace only, not for the entire LLMC config file.  
- `desktop_telemetry` exposes summary metrics such as number of files read, bytes moved, search calls, and top commands, using LLMC metrics and TE telemetry.  
- Telemetry queries can be filtered by `agent_id` using LLMC's logs and metrics; TE telemetry remains agent-agnostic but can be correlated by opaque IDs if needed.

## 5. Capability mapping

This section maps Desktop Commander functions to LLMC Desktop tools.

### 5.1 Configuration

- Desktop Commander: `get_config`, `set_config_value`  
- LLMC Desktop: `desktop_config.get`, `desktop_config.set`  

Implementation:

- Config lives under a new section in `llmc.toml`, for example:

```toml
[desktop_agent]
enabled = true
mode = "local"
allowed_roots = ["/home/dave", "/mnt/data/projects"]
allowed_commands = ["git", "python", "pytest", "rg", "ls", "cat"]
blocked_commands = ["rm", "shutdown", "reboot", "dd", "mkfs", "chmod", "chown"]
max_file_bytes = 1048576
max_output_bytes = 1048576
search_default_limit = 200

# Global retention policy for LLMC-managed process artifacts
process_artifact_retention_hours = 24
```

- `desktop_config.get` returns this section (filtered by caller identity if needed).  
- `desktop_config.set` allows updating a safe subset at runtime (for example `search_default_limit` or `max_output_bytes`).  
- Future extension: allow per-agent sections, for example `[desktop_agent.claude_desktop]`, keyed by `agent_id`.

### 5.2 Files and directories

- Desktop Commander: `read_file`, `read_multiple_files`, `write_file`, `create_directory`, `list_directory`, `move_file`, `get_file_info`.  
- LLMC Desktop: `desktop_fs.read_file`, `desktop_fs.read_multiple`, `desktop_fs.write_file`, `desktop_fs.create_directory`, `desktop_fs.list_directory`, `desktop_fs.move`, `desktop_fs.stat`.

Key design points:

- All paths are normalized and forced to stay under `allowed_roots`.  
- Device files and sockets are rejected.  
- Large file reads use TE or LLMC style envelopes with handles and paging instead of dumping entire files into the context.  
- Writes are constrained by `max_file_bytes` and limited per call to prevent giant patches.  
- File info returns safe metadata only (size, mode, timestamps, owner, basic flags).  
- If configured, edits generate backup files in per-agent artifact directories that will be automatically deleted after 24 hours by the LLMC cleanup job.

### 5.3 Search

- Desktop Commander: `start_search`, `get_more_search_results`, `stop_search`, `list_searches`.  
- LLMC Desktop: `desktop_search.start`, `desktop_search.get_more`, `desktop_search.stop`, `desktop_search.list`.

Key design points:

- Implementation uses TE's grep/find handler with ripgrep under the hood.  
- Results are ranked and truncated; the envelope includes:  
  - total matches (approximate)  
  - top N hits with file path, line number, and small excerpt  
  - handle for more (TE handle or LLMC handle).  
- Search sessions are cached in a per-agent registry with per-session and global limits to prevent runaway cost.  
- Search paths are automatically restricted to `allowed_roots`.  
- TE remains blind to `agent_id`; LLMC enforces per-agent behavior via its own search registry.  
- Any TE-generated on-disk search artifacts follow TE's own retention; LLMC's process cleanup only covers LLMC-managed artifacts.

### 5.4 Processes and sessions

- Desktop Commander: `start_process`, `read_process_output`, `interact_with_process`, `force_terminate`, `list_sessions`, `list_processes`, `kill_process`.  
- LLMC Desktop: `desktop_process.start`, `desktop_process.read_output`, `desktop_process.send_input`, `desktop_process.force_terminate`, `desktop_process.list_sessions`, `desktop_process.list_processes`, `desktop_process.kill`.

Key design points:

- Commands are validated against an allowlist plus blocked commands.  
- Long running processes have:  
  - configurable max runtime  
  - configurable max output bytes  
  - idle timeout.  
- Output is streamed and summarized with an LLMC envelope: the agent sees the most important lines first, with a handle for the raw buffer.  
- **No process sharing:**  
  - Process sessions are scoped to `agent_id`.  
  - An agent only sees its own processes in list calls and can only control processes it created.  
- Process logs and related artifacts are written under per-agent directories (for example `.llmc/desktop/process/<agent_id>/...`) and automatically deleted after the configured retention period (default 24 hours) by LLMC's cleanup job.

### 5.5 Editing and patching

- Desktop Commander: `edit_block`.  
- LLMC Desktop: `desktop_fs.edit_block`.

Key design points:

- Edits are structured: the agent provides a patch spec with target file, locate strategy (by line range or anchor text plus offset), and replacement text.  
- Before and after snapshots can be logged to per-agent artifact directories, subject to the 24h cleanup rule.  
- For code files under LLMC's graph, edits can optionally trigger a lightweight reindex.

### 5.6 Telemetry and feedback

- Desktop Commander: `get_usage_stats`, `get_recent_tool_calls`, `give_feedback_to_desktop_commander`.  
- LLMC Desktop: `desktop_telemetry.get_usage_stats`, `desktop_telemetry.get_recent_calls`, `desktop_telemetry.give_feedback`.

Key design points:

- Implementation reuses TE telemetry (agent-agnostic) plus LLMC metrics (agent-aware).  
- Feedback is stored in a simple local log and optionally indexed into LLMC's RAG so future agents can see "what worked" and "what broke".  
- Telemetry can be filtered by `agent_id` using LLMC logs and metrics; TE telemetry is correlated via opaque IDs only if needed.

### 5.7 Prompts and guidance

- Desktop Commander: `get_prompts` plus static context document.  
- LLMC Desktop: guidance is split between AGENTS.md, an agent sidecar, and a small "desktop_prompts" payload in the MCP tool description.

Key design points:

- The MCP tool descriptions for the desktop tools will carry short, strict instructions on when to use each tool family.  
- Long form guidance lives in the agent config and is injected by LLMC, not by MCP.  
- Agent guidance can explicitly call out that processes are not shared and that LLMC-managed process artifacts are short-lived (24h retention).

## 6. Security model

Security constraints must be at least as strict as Desktop Commander:

- Paths: all desktop tool calls must resolve paths under `allowed_roots`. Any attempt to escape (`..`, symlink chains) results in a hard error.  
- Commands: only commands in `allowed_commands` are permitted; `blocked_commands` always win in case of overlap.  
- File size and output size: enforced per call and per session.  
- Environment: MCP and TE run with a restricted environment that excludes secrets unless explicitly opted in for a given agent.  
- Network: desktop tools are not allowed to open network sockets; they operate on local files and processes only.  
- Agent isolation:  
  - Process sessions are scoped to `agent_id`.  
  - LLMC-managed logs and artifacts are stored per-agent.  
  - No process sharing or cross-agent list/control is allowed.  
- TE remains a **non-security boundary**:  
  - TE does not know which agent is calling it.  
  - All security decisions are enforced by LLMC before TE is invoked.

Configured policies are visible via `desktop_config` but write access is tightly scoped.

## 7. Observability

The desktop tool layer emits:

- Structured logs via `JsonLogFormatter`, including session id, agent id, tool name, action, path or command, success flag, and duration.  
- Metrics via `MetricsCollector`, including counts and histograms for file bytes read, search calls, process starts, artifacts created, and failures.  
- TE telemetry, which tracks commands and performance without agent identity.

A periodic cleanup task:

- Scans per-agent LLMC artifact directories (for example `.llmc/desktop/process/...`).  
- Deletes any LLMC-managed process-related artifact files older than `process_artifact_retention_hours` (default 24 hours).  
- Emits metrics on files deleted and any errors encountered.

These signals must be enough to support ruthlessly tested acceptance criteria, identify runaway agents, and keep disk usage under control.

## 8. Phased delivery plan

To keep the work shippable, implement this HLD in phases on top of the MCP MVP.

### Phase 1: Read-only desktop tools

- Implement `desktop_fs.read_file`, `desktop_fs.list_directory`, `desktop_fs.stat`, `desktop_fs.get_file_info`.  
- Implement `desktop_search.start` and `desktop_search.get_more` using TE search (agent-agnostic).  
- Wire config section and enforcement of `allowed_roots` and basic size limits.  
- Capture `agent_id` from `llmc_mcp` where available (initially `"claude_desktop"` for Desktop Commander).  
- Add minimal tests and smoke tests for these tools.

### Phase 2: Writes and editing

- Implement `desktop_fs.write_file`, `desktop_fs.create_directory`, `desktop_fs.move`, `desktop_fs.edit_block`.  
- Add safety features: backups for edits, max write sizes, and dry run mode for testing.  
- Persist edit backups under per-agent artifact directories.  
- Expand tests to cover `edit_block` and directory creation.

### Phase 3: Process management and cleanup

- Implement `desktop_process.start`, `desktop_process.read_output`, `desktop_process.send_input`, `desktop_process.force_terminate`, `desktop_process.list_processes`, `desktop_process.list_sessions`, `desktop_process.kill`.  
- Add per-agent process registry with timeouts and caps.  
- Implement the background cleanup job that:  
  - Reaps stale or zombie processes.  
  - Deletes any LLMC-managed process logs and artifacts older than 24 hours.  
- Add tests that run short lived commands (for example `ls`, `pytest -k smoke`) under the allowlist and validate that artifacts disappear after a forced low retention interval in test mode.

### Phase 4: Telemetry and polish

- Implement `desktop_telemetry.get_usage_stats`, `desktop_telemetry.get_recent_calls`, `desktop_telemetry.give_feedback`.  
- Link telemetry to LLMC metrics and to RAG indexing if desired.  
- Tighten error messages and documentation.  
- Update AGENTS.md and user guide to describe the new desktop agent capabilities, multi-agent behavior, and cleanup policy.  
- Tune retention defaults based on real usage.

## 9. Risks and mitigations

- **Risk:** Agents accidentally delete or overwrite important files.  
  - **Mitigation:** default to a conservative allowlist and blocked commands, enforce backups for edits, require explicit opt in for destructive commands.  

- **Risk:** Token usage creeps up due to verbose tool outputs.  
  - **Mitigation:** TE style enrichment and handle based paging are mandatory for all potentially large outputs. Include token estimates in metrics.

- **Risk:** Complexity explosion in the MCP tool surface.  
  - **Mitigation:** keep the tool families small and focused; do not expose every Desktop Commander tool as a separate MCP tool.

- **Risk:** Disk usage from process logs and artifacts grows over time.  
  - **Mitigation:** enforce per-agent LLMC artifact directories and a 24 hour cleanup policy, configurable via `llmc.toml`, monitored by metrics.

- **Risk:** TE accidentally becomes a de facto policy engine by leaking agent identity.  
  - **Mitigation:** TE is kept agent-agnostic; all policy and identity live in LLMC; TE sees at most opaque call/session IDs.

## 10. Open questions

- Do we need fully separate desktop configurations per agent in v1, or is a single `desktop_agent` section plus obvious future extension sufficient.  
- Should the 24 hour retention window be globally fixed or easily configurable per environment.  
- How aggressively should old search and process sessions be garbage collected beyond age-based deletion (for example count-based or size-based thresholds).  
- Do we want LLMC to periodically inspect TE's handle store for size/age, or is that left entirely to TE's own retention policies.

These questions can be resolved in the SDD and implementation phases without changing the core architecture defined here.
