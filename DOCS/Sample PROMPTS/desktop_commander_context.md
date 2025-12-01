# Desktop Commander - Complete Context Documentation

## Overview

Desktop Commander is a comprehensive file and process management system for local development and system administration tasks. It provides tools for file operations, process management, searching, and system configuration.

**Key Principles:**
- Always use absolute paths for reliability
- Paths are automatically normalized regardless of slash direction
- Relative paths may fail; they depend on current working directory
- Tilde paths (~/...) might not work in all contexts

---

## Configuration Management

### get_config
**Description:** Get the complete server configuration as JSON.

**Returns:**
- `blockedCommands` - Array of blocked shell commands
- `defaultShell` - Shell to use for commands
- `allowedDirectories` - Paths the server can access
- `fileReadLineLimit` - Max lines for read_file (default 1000)
- `fileWriteLineLimit` - Max lines per write_file call (default 50)
- `telemetryEnabled` - Boolean for telemetry opt-in/out
- `currentClient` - Information about currently connected MCP client
- `clientHistory` - History of all clients that have connected
- `version` - Version of the DesktopCommander
- `systemInfo` - Operating system and environment details

**Parameters:** None

**Usage:** Query current system configuration and constraints

---

### set_config_value
**Description:** Set a specific configuration value by key.

**⚠️ WARNING:** Should be used in a separate chat from file operations and command execution to prevent security issues.

**Parameters:**
- `key` (string, required) - Configuration key to set
- `value` (string | number | boolean | array | null) - New value

**Valid Keys:**
- `blockedCommands` (array)
- `defaultShell` (string)
- `allowedDirectories` (array of paths)
- `fileReadLineLimit` (number)
- `fileWriteLineLimit` (number)
- `telemetryEnabled` (boolean)

**⚠️ IMPORTANT:** Setting `allowedDirectories` to an empty array ([]) allows full access to the entire file system, regardless of operating system.

**Usage:** Configure system permissions and limits

---

## File Operations

### read_file
**Description:** Read contents of a file from the file system or a URL with optional offset and length parameters.

**Parameters:**
- `path` (string, required) - File path or URL
- `offset` (number, default: 0) - Start line (0-based indexing)
  - Positive: Start from line N
  - Negative: Read last N lines from end (tail behavior)
- `length` (number, default: configurable) - Max lines to read
  - Used with positive offsets for range reading
  - Ignored when offset is negative
- `isUrl` (boolean, default: false) - Set true for URL fetching

**Examples:**
- `offset: 0, length: 10` → First 10 lines
- `offset: 100, length: 5` → Lines 100-104
- `offset: -20` → Last 20 lines
- `offset: -5, length: 10` → Last 5 lines (length ignored)

**Performance Optimizations:**
- Large files with negative offsets use reverse reading
- Large files with deep positive offsets use byte estimation
- Small files use fast readline streaming

**Supported Image Types:** PNG, JPEG, GIF, WebP (displays as viewable images)

**Usage:** View file contents with optional range selection

---

### read_multiple_files
**Description:** Read contents of multiple files simultaneously.

**Parameters:**
- `paths` (array of strings, required) - File paths to read

**Features:**
- Each file's content returned with its path as reference
- Handles text files normally
- Renders images as viewable content
- Failed reads don't stop entire operation
- Recognized image types: PNG, JPEG, GIF, WebP

**Usage:** Batch read multiple files at once

---

### write_file
**Description:** Write or append to file contents.

**⚠️ CHUNKING IS STANDARD PRACTICE:** Always write files in chunks of 25-30 lines maximum. This is the normal, recommended way to write files.

**Standard Process for Any File:**
1. FIRST → `write_file(filePath, firstChunk, {mode: 'rewrite'})` [≤30 lines]
2. THEN → `write_file(filePath, secondChunk, {mode: 'append'})` [≤30 lines]
3. CONTINUE → `write_file(filePath, nextChunk, {mode: 'append'})` [≤30 lines]

**Parameters:**
- `path` (string, required) - File path
- `content` (string, required) - Content to write
- `mode` (enum: "rewrite" | "append", default: "rewrite")

**When to Chunk:**
1. Any file expected to be longer than 25-30 lines
2. When writing multiple files in sequence
3. When creating documentation, code files, or configuration files

**Performance Note:** Files over 50 lines generate performance notes but are still written successfully.

**Handling Continuation:**
- If operation is incomplete, read the file to see what was written
- Continue writing only remaining content using `mode: 'append'`
- Keep chunks to 25-30 lines each

**Usage:** Create or modify files with automatic chunking

---

### create_directory
**Description:** Create a new directory or ensure a directory exists.

**Parameters:**
- `path` (string, required) - Directory path

**Features:**
- Can create multiple nested directories in one operation
- Only works within allowed directories

**Usage:** Create directory structure

---

### list_directory
**Description:** Get a detailed listing of all files and directories in a specified path.

**Parameters:**
- `path` (string, required) - Directory path
- `depth` (number, default: 2) - Recursion depth
  - `depth=1`: Only direct contents
  - `depth=2`: Contents plus one level of subdirectories
  - `depth=3+`: Multiple levels deep

**Output Format:**
- `[DIR]` prefix for directories
- `[FILE]` prefix for files
- Full relative paths from root directory

**Context Overflow Protection:**
- Top-level directory shows ALL items
- Nested directories limited to 100 items maximum per directory
- Warning displayed when a nested directory has >100 items:
  `[WARNING] node_modules: 500 items hidden (showing first 100 of 600 total)`

**Example Output (depth=2):**
```
[DIR] src
[FILE] src/index.ts
[DIR] src/tools
[FILE] src/tools/filesystem.ts
```

**Access Denied:** Shows `[DENIED]` if directory cannot be accessed

**Usage:** Browse directory structure with controlled depth

---

### move_file
**Description:** Move or rename files and directories.

**Parameters:**
- `source` (string, required) - Source path
- `destination` (string, required) - Destination path

**Features:**
- Move files between directories
- Rename in single operation
- Both source and destination must be within allowed directories

**Usage:** Move or rename files and directories

---

### get_file_info
**Description:** Retrieve detailed metadata about a file or directory.

**Returns:**
- `size` - File size
- `creation time` - When created
- `last modified time` - Last modification timestamp
- `permissions` - File permissions
- `type` - File or directory type
- `lineCount` - For text files only
- `lastLine` - Zero-indexed number of last line (for text files)
- `appendPosition` - Line number for appending (for text files)

**Parameters:**
- `path` (string, required) - File or directory path

**Usage:** Get file metadata and statistics

---

## Search Operations

### start_search
**Description:** Start a streaming search that can return results progressively.

**Parameters:**
- `path` (string, required) - Search root directory
- `pattern` (string, required) - What to search for
- `searchType` (enum: "files" | "content", default: "files")
  - `"files"`: Find files by name
  - `"content"`: Search inside files for text patterns
- `filePattern` (string, optional) - Filter to specific file types (e.g., "*.js")
- `literalSearch` (boolean, default: false) - Exact string matching vs regex
- `ignoreCase` (boolean, default: true) - Case-insensitive search
- `includeHidden` (boolean, default: false) - Include hidden files
- `earlyTermination` (boolean, optional) - Stop early on exact match
- `contextLines` (number, default: 5) - Context lines for content search
- `maxResults` (number, optional) - Max results to return
- `timeout_ms` (number, optional) - Search timeout in milliseconds

**Search Strategy Guide:**

**USE searchType="files" WHEN:**
- User asks for specific files: "find package.json", "locate config files"
- Pattern looks like filename: "*.js", "README.md", "test-*.tsx"
- Want files by name/extension: "all TypeScript files", "Python scripts"
- Looking for configuration/setup files: ".env", "dockerfile", "tsconfig.json"

**USE searchType="content" WHEN:**
- Looking for code/logic: "authentication logic", "error handling", "API calls"
- Searching for functions/variables: "getUserData function", "useState hook"
- Finding text/comments: "TODO items", "FIXME comments", "documentation"
- Finding patterns in code: "console.log statements", "import statements"
- User describes functionality: "components handling login", "files with database queries"

**WHEN UNSURE:**
- Run TWO searches in parallel (files + content) for comprehensive coverage

**Pattern Matching Modes:**
- Default (literalSearch=false): Patterns treated as regular expressions
- Literal (literalSearch=true): Patterns treated as exact strings

**WHEN TO USE literalSearch=true:**
- Searching for code patterns with special characters
- Function calls with parentheses and quotes
- Array access with brackets
- Object methods with dots and parentheses
- File paths with backslashes
- Any pattern containing: `. * + ? ^ $ { } [ ] | \ ( )`

**Decision Framework:**
1. Generate keywords, avoiding low-confidence keywords
2. If 0 substantive keywords → Ask for clarification
3. If 1+ specific terms → Search with those terms
4. If only generic terms → Ask for specifics
5. If initial search limited → Try broader terms

**Examples:**
- "find package.json" → searchType="files", pattern="package.json"
- "find authentication components" → searchType="content", pattern="authentication"
- "locate all React components" → searchType="files", pattern="*.tsx|*.jsx"
- "find TODO comments" → searchType="content", pattern="TODO"
- "show me login files" → AMBIGUOUS → run both searches
- "find config" → AMBIGUOUS → run both (config files + files containing config code)

**Returns:** Session ID for progressive result retrieval

**Usage:** Start background search process; immediately returns with session ID

---

### get_more_search_results
**Description:** Get more results from an active search with offset-based pagination.

**Parameters:**
- `sessionId` (string, required) - Session ID from start_search
- `offset` (number, default: 0) - Start result index
  - Positive: Start from result N (0-based)
  - Negative: Read last N results from end
- `length` (number, default: 100) - Max results to read
  - Used with positive offsets for range
  - Ignored when offset is negative

**Examples:**
- `offset: 0, length: 100` → First 100 results
- `offset: 200, length: 50` → Results 200-249
- `offset: -20` → Last 20 results
- `offset: -5, length: 10` → Last 5 results

**Usage:** Paginate through search results

---

### stop_search
**Description:** Stop an active search gracefully.

**Parameters:**
- `sessionId` (string, required) - Session ID to stop

**Features:**
- Stops background search process
- Search still available for reading final results for 5 minutes
- Similar to force_terminate for terminal processes

**Usage:** Cancel search or stop when enough results found

---

### list_searches
**Description:** List all active searches.

**Returns:**
- Search IDs
- Search types
- Patterns
- Status
- Runtime

**Parameters:** None

**Usage:** View and manage multiple concurrent searches

---

## Process Management

### start_process
**Description:** Start a new terminal process with intelligent state detection.

**PRIMARY TOOL FOR FILE ANALYSIS AND DATA PROCESSING**

⚠️ **CRITICAL RULE:** For ANY local file work, ALWAYS use this tool + interact_with_process, NEVER use analysis/REPL tool.

**Parameters:**
- `command` (string, required) - Command to execute
- `shell` (string, optional) - Shell to use
- `timeout_ms` (number, required) - Timeout in milliseconds
- `verbose_timing` (boolean, optional) - Enable detailed performance telemetry

**Linux-Specific Notes:**
- Package managers vary: apt, yum, dnf, pacman, zypper
- Python 3 might be 'python3' command, not 'python'
- Standard Unix shell tools available (grep, awk, sed, etc.)
- File permissions important
- Systemd services common on modern distributions

**Required Workflow for Local Files:**
1. `start_process("python3 -i")` - Start Python REPL
2. `interact_with_process(pid, "import pandas as pd, numpy as np")`
3. `interact_with_process(pid, "df = pd.read_csv('/absolute/path/file.csv')")`
4. `interact_with_process(pid, "print(df.describe())")`
5. Continue analysis with pandas, matplotlib, seaborn, etc.

**Common File Analysis Patterns:**
- `start_process("python3 -i")` → Python REPL for data analysis (RECOMMENDED)
- `start_process("node -i")` → Node.js for JSON processing
- `start_process("cut -d',' -f1 file.csv | sort | uniq -c")` → Quick CSV analysis
- `start_process("wc -l /path/file.csv")` → Line counting
- `start_process("head -10 /path/file.csv")` → File preview

**Binary File Support:**
For PDF, Excel, Word, archives, databases, and other binary formats, use process tools with appropriate libraries or command-line utilities.

**Interactive Processes for Data Analysis:**
1. `start_process("python3 -i")` - Start Python REPL
2. `start_process("node -i")` - Start Node.js REPL
3. `start_process("bash")` - Start interactive bash shell
4. Use `interact_with_process()` to send commands
5. Use `read_process_output()` to get responses

**Smart Detection:**
- Detects REPL prompts (>>>, >, $, etc.)
- Identifies when process is waiting for input
- Recognizes process completion vs timeout
- Early exit prevents unnecessary waiting

**States Detected:**
- Process waiting for input (shows prompt)
- Process finished execution
- Process running (use read_process_output)

**Performance Debugging (verbose_timing parameter):**
Set verbose_timing: true to get:
- Exit reason (early_exit_quick_pattern, early_exit_periodic_check, process_exit, timeout)
- Total duration and time to first output
- Complete timeline of all output events with timestamps
- Which detection mechanism triggered early exit

**Returns:** Process ID (pid) for interaction

**Usage:** Start local file analysis or system command processes

---

### read_process_output
**Description:** Read output from a running process with intelligent completion detection.

**Parameters:**
- `pid` (number, required) - Process ID
- `timeout_ms` (number, optional) - Timeout in milliseconds
- `verbose_timing` (boolean, optional) - Enable detailed performance telemetry

**Smart Features:**
- Early exit when REPL shows prompt (>>>, >, etc.)
- Detects process completion vs still running
- Prevents hanging on interactive prompts
- Clear status messages about process state

**REPL Usage:**
- Stops immediately when REPL prompt detected
- Shows clear status: waiting for input vs finished
- Shorter timeouts needed due to smart detection
- Works with Python, Node.js, R, Julia, etc.

**Detection States:**
- Process waiting for input (ready for interact_with_process)
- Process finished execution
- Timeout reached (may still be running)

**Performance Debugging (verbose_timing parameter):**
Set verbose_timing: true to get:
- Exit reason (early_exit_quick_pattern, early_exit_periodic_check, process_finished, timeout)
- Total duration and time to first output
- Complete timeline of all output events with timestamps
- Which detection mechanism triggered early exit

**Usage:** Read output from running processes; intelligently detects when waiting for input

---

### interact_with_process
**Description:** Send input to a running process and automatically receive the response.

**⚠️ CRITICAL:** THIS IS THE PRIMARY TOOL FOR ALL LOCAL FILE ANALYSIS. For ANY local file analysis (CSV, JSON, data processing), ALWAYS use this instead of the analysis tool.

**FILE ANALYSIS PRIORITY ORDER (MANDATORY):**
1. ALWAYS FIRST: Use this tool for local data analysis
2. ALTERNATIVE: Use command-line tools (cut, awk, grep) for quick processing
3. NEVER EVER: Use analysis tool for local file access (IT WILL FAIL)

**Parameters:**
- `pid` (number, required) - Process ID from start_process
- `input` (string, required) - Code/command to execute
- `timeout_ms` (number, optional) - Max wait (default: 8000ms)
- `wait_for_prompt` (boolean, optional, default: true) - Auto-wait for response
- `verbose_timing` (boolean, optional) - Enable detailed performance telemetry

**Required Interactive Workflow for File Analysis:**
1. Start REPL: `start_process("python3 -i")`
2. Load libraries: `interact_with_process(pid, "import pandas as pd, numpy as np")`
3. Read file: `interact_with_process(pid, "df = pd.read_csv('/absolute/path/file.csv')")`
4. Analyze: `interact_with_process(pid, "print(df.describe())")`
5. Continue: `interact_with_process(pid, "df.groupby('column').size()")`

**Binary File Processing Workflows:**
Use appropriate Python libraries (PyPDF2, pandas, docx2txt, etc.) or command-line tools for binary file analysis.

**Smart Detection:**
- Automatically waits for REPL prompt (>>>, >, etc.)
- Detects errors and completion states
- Early exit prevents timeout delays
- Clean output formatting (removes prompts)

**Supported REPLs:**
- Python: `python3 -i` (RECOMMENDED for data analysis)
- Node.js: `node -i`
- R: `R`
- Julia: `julia`
- Shell: `bash`, `zsh`
- Database: `mysql`, `postgres`

**Performance Debugging (verbose_timing parameter):**
Set verbose_timing: true to get:
- Exit reason (early_exit_quick_pattern, early_exit_periodic_check, process_finished, timeout, no_wait)
- Total duration and time to first output
- Complete timeline of all output events with timestamps
- Which detection mechanism triggered early exit

**Returns:** Execution result with status indicators

**Usage:** Send commands to running processes; ALWAYS use for local file analysis

---

### force_terminate
**Description:** Force terminate a running terminal session.

**Parameters:**
- `pid` (number, required) - Process ID

**Usage:** Forcefully stop a process

---

### list_sessions
**Description:** List all active terminal sessions.

**Returns:**
- PID: Process identifier
- Blocked: Whether session is waiting for input
- Runtime: How long session has been running

**Debugging REPLs:**
- "Blocked: true" often means REPL is waiting for input
- Use to verify sessions running before sending input
- Long runtime with blocked status may indicate stuck process

**Parameters:** None

**Usage:** View active sessions and their status

---

### list_processes
**Description:** List all running processes.

**Returns:**
- PID
- Command name
- CPU usage
- Memory usage

**Parameters:** None

**Usage:** View all running processes with resource usage

---

### kill_process
**Description:** Terminate a running process by PID.

**⚠️ WARNING:** Use with caution as this forcefully terminates the specified process.

**Parameters:**
- `pid` (number, required) - Process ID

**Usage:** Terminate a specific process

---

## Text Editing

### edit_block
**Description:** Apply surgical text replacements to files.

**Best Practice:** Make multiple small, focused edits rather than one large edit. Each call should change only what needs to be changed.

**Parameters:**
- `file_path` (string, required) - Path to file
- `old_string` (string, required) - Text to replace
- `new_string` (string, required) - Replacement text
- `expected_replacements` (number, default: 1) - Number of expected matches

**Behavior:**
- By default, replaces only ONE occurrence
- To replace multiple occurrences, provide exact expected count
- Replaces one occurrence if count not specified

**Uniqueness Requirement:**
When expected_replacements=1 (default), include minimal context necessary (typically 1-3 lines) before and after change point, with exact whitespace and indentation.

**Multiple Changes:**
Make separate edit_block calls for each distinct change rather than one large replacement.

**Close Match Behavior:**
When close but non-exact match found, character-level diff shown in format:
`common_prefix{-removed-}{+added+}common_suffix`

**Performance Note:**
Configurable line limit (fileWriteLineLimit) warns if edited file exceeds limit. If this happens, consider breaking edits into smaller, more focused changes.

**Usage:** Surgically replace specific text in files

---

## Statistics and Feedback

### get_usage_stats
**Description:** Get usage statistics for debugging and analysis.

**Returns:** Summary of tool usage, success/failure rates, and performance metrics

**Parameters:** None

**Usage:** View tool call statistics and performance metrics

---

### get_recent_tool_calls
**Description:** Get recent tool call history with arguments and outputs.

**Parameters:**
- `maxResults` (number, default: 50, max: 1000) - Number of results
- `since` (datetime, optional) - Get calls after this datetime
- `toolName` (string, optional) - Filter to specific tool

**Returns:** Chronological list of tool calls made during session

**Use Cases:**
- Onboarding new chats about work already done
- Recovering context after chat history loss
- Debugging tool call sequences

**Note:** Does not track its own calls or other meta/query tools. History kept in memory (last 1000 calls, lost on restart).

**Usage:** View recent tool call history

---

## Feedback and Onboarding

### give_feedback_to_desktop_commander
**Description:** Open feedback form in browser to provide feedback about Desktop Commander.

**⚠️ IMPORTANT:** This tool simply opens the feedback form - no pre-filling available. User fills out form manually in browser.

**Workflow:**
1. When user agrees to give feedback, call this tool immediately
2. No need to ask questions or collect information
3. Tool opens form with auto-filled usage statistics:
   - tool_call_count: Number of commands made
   - days_using: How many days using Desktop Commander
   - platform: Operating system (Mac/Windows/Linux)
   - client_id: Analytics identifier

**Survey Questions Answered in Form:**
- Job title and technical comfort level
- Company URL for industry context
- Other AI tools used
- Desktop Commander's biggest advantage
- How typically used
- Recommendation likelihood (0-10)
- User study participation interest
- Email and additional feedback

**Parameters:** None (call immediately without asking questions first)

**Usage:** Collect user feedback

---

### get_prompts
**Description:** Retrieve a specific Desktop Commander onboarding prompt by ID and execute it.

**Simplified Onboarding V2:** Presents 5 options as numbered list

**Available Onboarding Options:**
1. Organize my Downloads folder (promptId: 'onb2_01')
2. Explain a codebase or repository (promptId: 'onb2_02')
3. Create organized knowledge base (promptId: 'onb2_03')
4. Analyze a data file (promptId: 'onb2_04')
5. Check system health and resources (promptId: 'onb2_05')

**Parameters:**
- `action` (enum: "get_prompt", required) - Action to perform
- `promptId` (string, required) - ID of prompt to retrieve
- `anonymous_user_use_case` (string, optional) - Goal/problem being solved

**Anonymous Use Case (RECOMMENDED):**
Infer what GOAL or PROBLEM the user is trying to solve from conversation history. Focus on job-to-be-done, not just what they're doing.

**GOOD (problem/goal focused):**
"automating backup workflow", "converting PDFs to CSV", "debugging test failures", "organizing project files", "monitoring server logs", "extracting data from documents"

**BAD (too vague or contains PII):**
"using Desktop Commander", "working on John's project", "fixing acme-corp bug"

**Default:** If unclear, use: "exploring tool capabilities"

**Behavior:**
- Prompt content injected
- Execution begins immediately

**Usage:** Execute onboarding prompts for guided workflows

---

## General Guidelines

### Path Handling
- **Always use absolute paths** for reliability
- Paths automatically normalized regardless of slash direction
- Relative paths may fail (depend on current working directory)
- Tilde paths (~/...) might not work in all contexts
- Unless explicitly asked for relative paths, use absolute paths

### File Access Control
- Only works within allowed directories
- Configuration limits based on `allowedDirectories`
- Empty array ([]) allows full file system access

### Performance Considerations
- Large file operations use optimized algorithms
- Chunking recommended for write operations >30 lines
- Search operations support pagination for large result sets
- Process operations include intelligent early exit detection

### Error Handling
- Individual file read failures don't stop batch operations
- Non-UTF-8 files display hex escapes (e.g., \x84)
- Process operations detect completion states automatically

### Security Reminders
- Configuration changes should be separate from file operations
- Be cautious with force termination
- Monitor blocked commands via configuration

---

## Quick Reference

**File Operations:**
- `read_file` - View file contents
- `read_multiple_files` - Batch read files
- `write_file` - Create/modify files (use chunking)
- `create_directory` - Create directories
- `list_directory` - Browse directory structure
- `move_file` - Move/rename files
- `get_file_info` - Get file metadata
- `edit_block` - Surgical text replacements

**Searching:**
- `start_search` - Initiate search
- `get_more_search_results` - Paginate results
- `stop_search` - Cancel search
- `list_searches` - View active searches

**Process Management:**
- `start_process` - Start terminal/REPL
- `interact_with_process` - Send commands (PRIMARY FOR FILE ANALYSIS)
- `read_process_output` - Read output
- `force_terminate` / `kill_process` - Stop processes
- `list_sessions` / `list_processes` - View processes

**Configuration:**
- `get_config` - View configuration
- `set_config_value` - Update configuration

**Utilities:**
- `get_usage_stats` - View statistics
- `get_recent_tool_calls` - View call history
- `give_feedback_to_desktop_commander` - Send feedback
- `get_prompts` - Execute onboarding

---

**Last Updated:** December 2025
**Status:** Complete Reference Documentation
