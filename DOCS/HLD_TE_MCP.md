# HLD – Tool Envelope as MCP (TE-MCP)

Version: 1.0  
Owner: Dave (LLMC)  
Status: Draft  
Doc: `HLD_TE_MCP.md`

---

## 1. Executive Summary

**Problem:** MCPs bloat context from both ends.
- **Input bloat:** Tool definitions carry paragraphs of documentation per tool
- **Output bloat:** Raw command results fill context windows with noise

**Solution:** Build a lean MCP that exposes TE-enriched shell commands with minimal schema overhead.

**Key Insight:** LLMs already know Unix. They don't need 500 tokens explaining what `grep` does—they need 30 tokens telling them it exists and 50 tokens of enriched output telling them what's relevant.

---

## 2. The Context Tax Problem

### 2.1 Desktop Commander: A Case Study

Desktop Commander is one of the *better* MCPs. It's well-designed, actively maintained, and genuinely useful. Yet here's what it injects into every Claude session:

**Tool Count:** 24 tools  
**Estimated Schema Tokens:** ~18,000-22,000 tokens (loaded every message)

**Sample Tool Definition (read_file):**

```
Read the contents of a file from the file system or a URL with optional offset 
and length parameters.

Prefer this over 'execute_command' with cat/type for viewing files.

Supports partial file reading with:
- 'offset' (start line, default: 0)
  * Positive: Start from line N (0-based indexing)
  * Negative: Read last N lines from end (tail behavior)
- 'length' (max lines to read, default: configurable via 'fileReadLineLimit' 
  setting, initially 1000)
  * Used with positive offsets for range reading
  * Ignored when offset is negative (reads all requested tail lines)

Examples:
- offset: 0, length: 10     → First 10 lines
- offset: 100, length: 5    → Lines 100-104
- offset: -20               → Last 20 lines  
- offset: -5, length: 10    → Last 5 lines (length ignored)

Performance optimizations:
- Large files with negative offsets use reverse reading for efficiency
- Large files with deep positive offsets use byte estimation
- Small files use fast readline streaming

When reading from the file system, only works within allowed directories.
Can fetch content from URLs when isUrl parameter is set to true
(URLs are always read in full regardless of offset/length).

Handles text files normally and image files are returned as viewable images.
Recognized image types: PNG, JPEG, GIF, WebP.

IMPORTANT: Always use absolute paths for reliability...
```

**That's ~350 tokens for ONE tool.** Multiply by 24 tools.

### 2.2 What's Actually Load-Bearing?

Analyzing DC's schemas, the content breaks into:

| Category | % of Schema | Load-Bearing? |
|----------|-------------|---------------|
| Core function name/params | 10% | Yes |
| Brief purpose statement | 5% | Yes |
| Exhaustive examples | 30% | Mostly no |
| Edge case documentation | 25% | Sometimes |
| Warnings and caveats | 20% | Rarely |
| Cross-references | 10% | No |

**The brutal truth:** LLMs trained on billions of shell interactions don't need 20 tokens explaining what `offset` means. They know.

### 2.3 The Math

```
Desktop Commander Context Tax:
─────────────────────────────────
Tool schemas:          ~20,000 tokens
Loaded per message:    Yes
100-message session:   2,000,000 token overhead
At $3/MTok input:      $6 just for tool definitions

TE-MCP Target:
─────────────────────────────────
Tool schemas:          ~2,000 tokens (90% reduction)
Same capability:       Yes (LLM knows Unix)
100-message session:   200,000 token overhead
At $3/MTok input:      $0.60
```

---

## 3. Two-Sided Context Optimization

TE-MCP attacks context bloat from both directions:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT WINDOW                                │
├─────────────────────────────────────────────────────────────────┤
│  INPUT SIDE              │  OUTPUT SIDE                         │
│  (tool definitions)      │  (command results)                   │
│                          │                                      │
│  Traditional MCP:        │  Traditional MCP:                    │
│  [████████████████]      │  [████████████████████████████████]  │
│  20K tokens/session      │  Unbounded raw output                │
│                          │                                      │
│  TE-MCP:                 │  TE-MCP:                             │
│  [██]                    │  [████████]                          │
│  2K tokens/session       │  Ranked, breadcrumbed, budgeted      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Input Side: Minimal Tool Schemas

**Principle:** The LLM's weights ARE the documentation.

**DC's grep-equivalent (start_search):** ~600 tokens
**TE-MCP target:** ~60 tokens

```json
{
  "name": "te_grep",
  "description": "Search file contents. Returns ranked matches with truncation.",
  "parameters": {
    "pattern": {"type": "string"},
    "path": {"type": "string", "optional": true}
  }
}
```

That's it. The LLM knows what grep does. The response teaches the rest.

### 3.2 Output Side: MPD Response Format

TE already does this (see SDD_Tool_Envelope_v1.2.md):

```
# TE_BEGIN_META
{"v":1,"cmd":"grep","matches":847,"truncated":true,"handle":"res_01H..."}
# TE_END_META

tools/rag/database.py:15: def database_connection():  # definition
tools/rag/database.py:89: database_connection.execute(  # hot usage

# TE: 612 more in tools/rag/, 235 elsewhere
```

The response stream *is* the teaching.

---

## 4. Architecture


### 4.1 System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MCP Client                                    │
│  (Claude Desktop, Continue, Cline, ChatGPT via MCPO, etc.)           │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │ JSON-RPC (stdio or SSE)
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      TE-MCP Server                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│  │ Lean Schema │  │   Router    │  │  Response   │                   │
│  │  Registry   │  │             │  │  Formatter  │                   │
│  └─────────────┘  └──────┬──────┘  └─────────────┘                   │
│                          │                                            │
│                          ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    TE Core (existing)                        │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │     │
│  │  │ Handlers │  │ Sniffer  │  │  Store   │  │Telemetry │     │     │
│  │  │grep,cat..│  │          │  │ (handles)│  │          │     │     │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │     │
│  └─────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         Underlying Tools
                      (rg, cat, find, etc.)
```

### 4.2 Components

**C1 – Schema Registry**
- Holds minimal tool definitions
- No examples, no edge cases, no warnings
- Just: name, brief purpose, parameters

**C2 – MCP Protocol Handler**
- JSON-RPC over stdio (primary)
- Optional SSE for remote (MCPO bridge)
- Handles tool listing, tool invocation

**C3 – TE Core (existing)**
- Handlers, sniffer, store, telemetry
- No changes needed—TE-MCP is a thin wrapper

**C4 – Response Formatter**
- Converts TE's FormattedOutput to MCP tool_result
- Preserves MPD structure in response

### 4.3 Tool Inventory

**Phase 1 - Core Shell (MVP):**

| Tool | Description (target: <15 words) |
|------|--------------------------------|
| `te_grep` | Search file contents. Returns ranked matches. |
| `te_cat` | View file with content-type-aware preview. |
| `te_find` | Find files by name pattern. |
| `te_ls` | List directory contents with type info. |
| `te_head` | First N lines of file. |
| `te_tail` | Last N lines of file. |
| `te_handle` | Retrieve stored result by handle ID. |

**Phase 2 - RAG Integration:**

| Tool | Description |
|------|-------------|
| `te_rag` | Semantic search over indexed codebase. |
| `te_explain` | Get enriched explanation of code symbol. |

**Phase 3 - Advanced:**

| Tool | Description |
|------|-------------|
| `te_diff` | Compare files with semantic grouping. |
| `te_git` | Git operations with relevant context. |

---

## 5. Minimal Schema Design

### 5.1 Design Principles

1. **No examples in schema** – LLM knows grep
2. **No edge case warnings** – handle in response
3. **No cross-references** – single tool, single purpose
4. **Brief descriptions** – 10-15 words max
5. **Flat parameters** – avoid nested objects

### 5.2 Schema Template

```json
{
  "name": "te_{cmd}",
  "description": "{10-15 word purpose}. {one key behavior}.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param1": {"type": "string", "description": "{3-5 words}"},
      "param2": {"type": "string"}
    },
    "required": ["param1"]
  }
}
```

### 5.3 Full Schema Examples

**te_grep:**
```json
{
  "name": "te_grep",
  "description": "Search file contents for pattern. Returns ranked, truncated matches.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pattern": {"type": "string", "description": "Regex pattern"},
      "path": {"type": "string", "description": "Search path (optional)"},
      "raw": {"type": "boolean", "description": "Bypass enrichment"}
    },
    "required": ["pattern"]
  }
}
```
**Token count:** ~65 tokens

**te_cat:**
```json
{
  "name": "te_cat",
  "description": "View file contents with smart preview. Large files truncated with handle.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "lines": {"type": "integer", "description": "Max lines to show"}
    },
    "required": ["path"]
  }
}
```
**Token count:** ~55 tokens

**te_handle:**
```json
{
  "name": "te_handle", 
  "description": "Retrieve previously truncated result by handle ID.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "handle": {"type": "string"},
      "chunk": {"type": "integer", "description": "Chunk number (optional)"}
    },
    "required": ["handle"]
  }
}
```
**Token count:** ~50 tokens

### 5.4 Comparison: DC vs TE-MCP

| Metric | Desktop Commander | TE-MCP |
|--------|-------------------|--------|
| Tools | 24 | 7 (Phase 1) |
| Avg tokens/tool | ~750 | ~60 |
| Total schema tokens | ~18,000 | ~420 |
| Reduction | baseline | **97.7%** |

---

## 6. Response Format


### 6.1 MCP Tool Result Structure

MCP requires tool results in this format:

```json
{
  "content": [
    {
      "type": "text",
      "text": "..."
    }
  ],
  "isError": false
}
```

TE-MCP embeds the existing TE format inside:

```json
{
  "content": [
    {
      "type": "text", 
      "text": "# TE_BEGIN_META\n{\"v\":1,\"cmd\":\"grep\",\"matches\":847,\"truncated\":true,\"handle\":\"res_01H...\"}\n# TE_END_META\n\ntools/rag/database.py:15: def database_connection():\ntools/rag/service.py:23: from .database import database_connection\n\n# TE: 845 more matches, use handle to retrieve"
    }
  ]
}
```

### 6.2 Error Handling

```json
{
  "content": [
    {
      "type": "text",
      "text": "# TE_BEGIN_META\n{\"v\":1,\"cmd\":\"grep\",\"error\":\"invalid_pattern\"}\n# TE_END_META\n\n[TE] Invalid regex pattern: unbalanced parenthesis"
    }
  ],
  "isError": true
}
```

---

## 7. Implementation

### 7.1 Technology Choice

**Python** – Matches existing TE codebase, simple MCP SDK available.

Dependencies:
- `mcp` – Official MCP Python SDK
- Existing TE modules (no changes)

### 7.2 Server Entry Point

```python
# llmc/te/mcp_server.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from .cli import dispatch_command
from .schemas import TOOL_SCHEMAS

server = Server("te-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_SCHEMAS

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Strip 'te_' prefix, dispatch to existing TE
    cmd = name.replace("te_", "")
    result = dispatch_command(cmd, arguments)
    return [TextContent(type="text", text=result.to_string())]

def main():
    import asyncio
    asyncio.run(server.run())
```

### 7.3 Schema Registry

```python
# llmc/te/schemas.py

from mcp.types import Tool

TOOL_SCHEMAS = [
    Tool(
        name="te_grep",
        description="Search file contents for pattern. Returns ranked, truncated matches.",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "path": {"type": "string", "description": "Search path"},
                "raw": {"type": "boolean", "description": "Bypass enrichment"}
            },
            "required": ["pattern"]
        }
    ),
    Tool(
        name="te_cat",
        description="View file contents with smart preview. Large files truncated.",
        inputSchema={
            "type": "object", 
            "properties": {
                "path": {"type": "string"},
                "lines": {"type": "integer"}
            },
            "required": ["path"]
        }
    ),
    # ... more tools
]
```

### 7.4 File Structure

```
llmc/te/
├── __init__.py
├── cli.py              # Existing CLI
├── config.py           # Existing config
├── formatter.py        # Existing formatter  
├── sniffer.py          # Existing sniffer
├── store.py            # Existing store
├── telemetry.py        # Existing telemetry
├── handlers/           # Existing handlers
│   ├── __init__.py
│   ├── grep.py
│   ├── cat.py          # New
│   ├── find.py         # New
│   └── ls.py           # New
├── mcp_server.py       # NEW: MCP server
└── schemas.py          # NEW: Minimal schemas
```

---

## 8. Desktop Commander Schema Analysis

### 8.1 Raw Data (Extracted from Live Context)

Below are actual DC tool definitions as loaded into Claude's context. This is what you're paying for:

**Top 5 Token-Heavy Tools:**

| Tool | Est. Tokens | Primary Bloat Source |
|------|-------------|---------------------|
| `start_process` | ~900 | Extensive examples, workflow guides |
| `interact_with_process` | ~850 | Duplicates start_process content |
| `start_search` | ~800 | Search strategy guide embedded |
| `read_file` | ~350 | Offset/length examples |
| `write_file` | ~400 | Chunking instructions |

**Patterns of Bloat:**

1. **Example Proliferation**
   ```
   Examples:
   - offset: 0, length: 10     → First 10 lines
   - offset: 100, length: 5    → Lines 100-104
   - offset: -20               → Last 20 lines  
   - offset: -5, length: 10    → Last 5 lines (length ignored)
   ```
   LLMs trained on millions of pagination examples don't need this.

2. **Strategy Guides in Schemas**
   The `start_search` tool contains a full "SEARCH STRATEGY GUIDE" with 
   decision trees. This is prompt engineering, not schema definition.

3. **Cross-Tool Instructions**
   Tools reference each other: "Prefer this over 'execute_command' with 
   cat/type". This creates dependency chains in the schema.

4. **Defensive Documentation**
   "IMPORTANT: Always use absolute paths for reliability" appears in 
   nearly every tool. Once is enough—or zero times.

### 8.2 What TE-MCP Learns From This

1. **Schema is not documentation** – Documentation goes in docs.
2. **Examples teach at invocation time** – Put them in responses, not schemas.
3. **Trust the weights** – LLMs know Unix better than your examples.
4. **One tool, one job** – No strategy guides in schemas.

---

## 9. Client Compatibility

### 9.1 Tested Targets

| Client | Protocol | Status |
|--------|----------|--------|
| Claude Desktop | stdio | Primary target |
| Continue | stdio | Should work |
| Cline | stdio | Should work |
| ChatGPT (via MCPO) | SSE | Secondary target |
| Custom agents | stdio/SSE | Supported |

### 9.2 MCPO Bridge

For ChatGPT and other non-MCP clients:

```json
// mcp/te-mcp.config.json
{
  "description": "LLMC TE-MCP - Lean shell tools with enrichment",
  "mcpServers": {
    "te-mcp": {
      "command": "python",
      "args": ["-m", "llmc.te.mcp_server"],
      "env": {
        "TE_AGENT_ID": "chatgpt-mcpo"
      }
    }
  }
}
```

---

## 10. Phasing

### Phase 0 – Foundation (1-2 days)
- [ ] `mcp_server.py` skeleton
- [ ] `schemas.py` with te_grep only
- [ ] Wire to existing grep handler
- [ ] Test with Claude Desktop

### Phase 1 – Core Tools (3-5 days)
- [ ] Add te_cat, te_find, te_ls handlers
- [ ] Add te_head, te_tail handlers  
- [ ] Add te_handle for result retrieval
- [ ] Schema registry complete
- [ ] Telemetry captures MCP source

### Phase 2 – RAG Integration (1 week)
- [ ] te_rag tool exposing RAG search
- [ ] te_explain for symbol lookup
- [ ] Coach learns MCP vs CLI patterns

### Phase 3 – Polish (ongoing)
- [ ] MCPO bridge testing
- [ ] Performance tuning
- [ ] Schema optimization based on telemetry

---

## 11. Success Criteria

1. **Schema tokens < 500** for Phase 1 tools
2. **Same functionality** as DC equivalents  
3. **Works with Claude Desktop** out of box
4. **Telemetry captures** MCP invocations
5. **LLMs figure it out** without extra prompting

---

## 12. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Schema too minimal, LLM confused | Medium | Add tokens incrementally based on failure telemetry |
| MCP SDK instability | Low | SDK is simple, can fork if needed |
| Handle persistence across sessions | Medium | Accept limitation initially, add persistence later |
| Client compatibility issues | Low | Test with Claude Desktop first |

---

## 13. Appendix: DC Tool Definition Samples

### A.1 read_file (350 tokens)

```
Read the contents of a file from the file system or a URL with optional 
offset and length parameters.

Prefer this over 'execute_command' with cat/type for viewing files.

Supports partial file reading with:
- 'offset' (start line, default: 0)
  * Positive: Start from line N (0-based indexing)  
  * Negative: Read last N lines from end (tail behavior)
- 'length' (max lines to read, default: configurable via 'fileReadLineLimit' 
  setting, initially 1000)
...
[continues for 25+ more lines]
```

### A.2 TE-MCP Equivalent (55 tokens)

```json
{
  "name": "te_cat",
  "description": "View file contents with smart preview. Large files truncated.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "lines": {"type": "integer"}
    },
    "required": ["path"]
  }
}
```

**Reduction: 84%**

---

## 14. References

- `SDD_Tool_Envelope_v1.2.md` – TE core design
- `HLD_TE_Analytics_TUI.md` – Telemetry dashboard
- MCP Specification: https://modelcontextprotocol.io/
- Desktop Commander: https://github.com/wonderwhy-er/DesktopCommanderMCP
