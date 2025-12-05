# MCP Server Design Decisions

This document captures important design decisions in the LLMC MCP server implementation and explains the rationale behind choices that might appear unconventional.

---

## DD-MCP-001: Conditional Bootstrap Tool Description

**File:** `llmc_mcp/server.py`  
**Date:** 2025-12-05  
**Status:** Active

### Decision

The `00_INIT` bootstrap tool uses conditional language ("IF YOU HAVE NOT BEEN GIVEN MCP INSTRUCTIONS") rather than unconditional urgency ("EXECUTE IMMEDIATELY").

### Context

The MCP protocol has two ways to deliver startup instructions to agents:
1. **Server `instructions` field** - Delivered during MCP handshake (used by some clients like Antigravity)
2. **Bootstrap tool** - Called on-demand by the agent

Different MCP clients behave differently:
- **Antigravity/Gemini Code Assist**: Delivers `instructions` during handshake
- **Desktop Commander + Anthropic**: Does NOT deliver instructions automatically

### Problem

The original description was:
```
"⚠️ CRITICAL P0: EXECUTE THIS TOOL IMMEDIATELY ON SESSION START BEFORE ANY OTHER TOOL CALLS"
```

This caused a **race condition**:
1. Agent sees "CRITICAL P0 IMMEDIATELY" 
2. Agent panics and races to call the tool
3. MCP server not fully initialized yet
4. 💥 Session crash with "Agent execution terminated due to error"

### Solution

Changed to conditional phrasing:
```
"⚠️ P0 CRITICAL: IF YOU HAVE NOT BEEN GIVEN MCP INSTRUCTIONS, USE THIS TOOL ON STARTUP TO GET CONTEXT."
```

### Rationale

1. **Conditional logic breaks the race**: Agents that already received instructions via handshake won't rush to call it
2. **Still urgent for agents that need it**: Desktop Commander users will still call it since they have no instructions
3. **No behavior change for well-behaved clients**: The tool still works the same way when called

### Consequences

- **Benefit**: Eliminates race condition crashes in Antigravity/Gemini sessions
- **Benefit**: Still works correctly with Desktop Commander + Anthropic
- **Trade-off**: Agents might skip calling it when they shouldn't (mitigated by explicit "Skip if you already received server instructions")
- **Risk**: If an agent fails to get instructions through either path, it may operate without context

### Testing Considerations

When testing MCP clients, verify:
1. Agents with handshake instructions → Should NOT call `00_INIT`
2. Agents without handshake instructions → SHOULD call `00_INIT`
3. Both paths → Should result in agent having full bootstrap context

---

## DD-MCP-002: Code Execution Mode vs Classic Mode

**File:** `llmc_mcp/server.py`  
**Date:** 2025-12-04  
**Status:** Active

### Decision

Support two operational modes: Classic (23+ tools exposed) and Code Execution (3 bootstrap tools + execute_code).

### Context

Large tool manifests consume significant tokens. Anthropic's "code mode" pattern reduces this by exposing a Python execution environment where tools are importable stubs.

### Rationale

1. **98% token reduction**: Classic mode sends 23 tool definitions. Code mode sends 4.
2. **Dynamic discovery**: Agents read stub files to understand available functionality
3. **Backward compatibility**: Classic mode still works for clients that prefer explicit tools

### Consequences

- **Benefit**: Dramatic token savings for long sessions
- **Trade-off**: Agents must understand the stub import pattern
- **Note**: Stubs are generated at startup in `.llmc/stubs/`

---

## How to Use This Document

### For Developers
Reference this document when you encounter MCP code patterns that seem unusual. These are deliberate choices with specific rationale.

### For Testing Agents
Before flagging an MCP pattern as a bug, check if it's documented here. If the code matches a design decision, it's working as intended.

### For Reviewers
This document explains non-obvious design choices. Use it to understand the "why" behind implementation details.

---

## Contributing

When making a significant design decision that deviates from common patterns:
1. Add an entry to this document
2. Include inline comments in the code
3. Reference this document in code comments

**Format:**
```
## DD-MCP-XXX: [Short Title]
**File:** [File path]
**Date:** [YYYY-MM-DD]
**Status:** [Active|Superseded|Deprecated]

### Decision
[What was decided]

### Context
[Why this decision was needed]

### Rationale
[Why this approach was chosen]

### Consequences
[Trade-offs and implications]
```
