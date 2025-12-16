# High-Level Design: LLMC TUI Agent

**Version:** 0.1.0-draft  
**Date:** 2025-12-08  
**Author:** David Carroll + Antigravity  
**Status:** Planning

---

## 1. Executive Summary

This document describes the architecture for a **TUI-first agentic coding assistant** built on the LLMC infrastructure. Unlike existing tools (opencode, aider, Claude Code), this system is designed from the ground up for:

- **Small model operation** — 4B-8B parameter models on 8GB VRAM
- **Frugal context management** — every token counts
- **Progressive tool disclosure** — expose only what's needed
- **TUI as brain, GUI as hands** — the agent controls GUIs, not the other way around

---

## 2. Philosophy

### 2.1 The Problem with Current Tools

| Tool | Problem |
|------|---------|
| opencode | Dumps all 15+ tools on every request. Assumes frontier model context. |
| aider | Great at what it does, but bakes in their workflow, not yours. |
| Claude Code | Anthropic's walled garden. TypeScript stack. Claude-only. |
| Gemini CLI | Google's walled garden. Not extensible. |

All of these assume:
- Unlimited context windows (128K+)
- Frontier model intelligence
- API budget doesn't matter
- "Just throw tokens at it"

### 2.2 Our Philosophy

```
Unix 1970:                          LLMC Agent 2025:
───────────                         ────────────────
Do one thing well.                  Expose one tool at a time.
Text is universal.                  TUI is the control plane.
Compose small tools.                Agent composes tool calls.
Respect resource limits.            Every token is precious.
```

**Core Principle:** The agent runs lean on modest hardware. It puppets GUIs and browsers when needed, but the brain lives in the terminal.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                             │
├───────────────┬─────────────────────┬───────────────────────────────┤
│  Textual TUI  │  VS Code Extension  │  Neovim Plugin (future)       │
│  (native)     │  (webview/terminal) │                               │
└───────┬───────┴──────────┬──────────┴───────────────────────────────┘
        │                  │
        │    JSON-RPC / MCP Protocol / stdio
        │                  │
        ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AGENT CORE                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Session Manager                           │   │
│  │  - Conversation history                                      │   │
│  │  - Context window tracking                                   │   │
│  │  - Compaction triggers                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Agent Loop                                │   │
│  │  - Prompt assembly                                           │   │
│  │  - Model inference (local Ollama / remote)                   │   │
│  │  - Response streaming                                        │   │
│  │  - Tool call dispatch                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │               Progressive Tool Disclosure                    │   │
│  │  - Tier 0: Core tools (read, search, respond)                │   │
│  │  - Tier 1: Edit tools (unlocked on request)                  │   │
│  │  - Tier 2: System tools (bash, git, etc.)                    │   │
│  │  - Tier 3: External tools (browser, APIs)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
        │
        │ MCP Protocol
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LLMC BACKEND                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   RAG Core   │  │  Embeddings  │  │  Enrichment  │              │
│  │  (retrieval) │  │   (search)   │  │  (summaries) │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  MCP Tools   │  │   mcgrep     │  │  Repo Index  │              │
│  │  (exposed)   │  │  (semantic)  │  │  (SQLite)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
        │
        │ Controls (via tools)
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SYSTEMS                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   VS Code    │  │   Browser    │  │   Terminal   │              │
│  │  (editor)    │  │  (web ops)   │  │   (bash)     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │     Git      │  │   File I/O   │  │   Desktop    │              │
│  │              │  │              │  │   (future)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Progressive Tool Disclosure

### 4.1 The Problem

Current tools expose ALL capabilities to the model on every request:

```
opencode: 15 tools × ~500 tokens/tool = 7,500 tokens just for tool schemas
```

A 4B model with 8K context has ~6,500 tokens left for actual conversation. Unworkable.

### 4.2 The Solution: Tiered Tools

```python
TOOL_TIERS = {
    0: ["read", "search", "respond"],           # ~500 tokens
    1: ["edit", "write", "create"],             # Unlocked on edit intent
    2: ["bash", "git"],                         # Unlocked on system intent
    3: ["browser", "fetch", "mcp_external"],    # Unlocked explicitly
}
```

**Tier 0** is always active (~500 tokens). Higher tiers are unlocked:
- Automatically based on intent detection
- Explicitly via a `request_tools(tier: int)` meta-tool
- Based on conversation history ("user often edits after searching")

### 4.3 Unlock Mechanism

```python
class ToolDispatcher:
    def __init__(self):
        self.active_tier = 0
        self.unlocked_tools = set(TOOL_TIERS[0])
    
    def unlock_tier(self, tier: int):
        """Progressively unlock tools up to specified tier."""
        for t in range(tier + 1):
            self.unlocked_tools.update(TOOL_TIERS[t])
    
    def get_active_tools(self) -> list[Tool]:
        """Return only currently unlocked tools for prompt assembly."""
        return [t for t in ALL_TOOLS if t.name in self.unlocked_tools]
```

### 4.4 Intent Detection (Optional Enhancement)

```python
INTENT_KEYWORDS = {
    "edit": ["change", "modify", "fix", "update", "refactor"],
    "system": ["run", "execute", "build", "test", "commit"],
    "browser": ["fetch", "download", "look up", "search web"],
}

def detect_intent(user_message: str) -> int:
    """Heuristic tier detection based on user message."""
    msg_lower = user_message.lower()
    
    if any(k in msg_lower for k in INTENT_KEYWORDS["browser"]):
        return 3
    if any(k in msg_lower for k in INTENT_KEYWORDS["system"]):
        return 2
    if any(k in msg_lower for k in INTENT_KEYWORDS["edit"]):
        return 1
    return 0
```

---

## 5. Agent Loop

### 5.1 Core Loop

```python
async def agent_loop(session: Session, user_message: str) -> AsyncIterator[str]:
    """Main agent loop with progressive disclosure."""
    
    # 1. Detect intent, adjust tool tier
    intent_tier = detect_intent(user_message)
    session.dispatcher.unlock_tier(intent_tier)
    
    # 2. Assemble context
    context = await assemble_context(
        session=session,
        user_message=user_message,
        max_tokens=session.model.context_limit - 1000,  # Reserve for response
    )
    
    # 3. Get active tools (only unlocked ones)
    tools = session.dispatcher.get_active_tools()
    
    # 4. Call model with streaming
    async for chunk in call_model(
        messages=context.messages,
        tools=tools,
        model=session.model,
    ):
        if chunk.type == "text":
            yield chunk.content
        elif chunk.type == "tool_call":
            result = await execute_tool(chunk.tool, chunk.args, session)
            # Inject result back into context for next iteration
            context.add_tool_result(chunk.id, result)
    
    # 5. Check if more tool calls needed
    if context.has_pending_tools():
        async for chunk in agent_loop(session, ""):  # Continue
            yield chunk
```

### 5.2 Context Assembly

```python
async def assemble_context(
    session: Session,
    user_message: str,
    max_tokens: int,
) -> Context:
    """Assemble context with frugal token management."""
    
    context = Context()
    
    # 1. System prompt (model-specific, from external file)
    system_prompt = load_prompt(session.model.family)  # e.g., qwen.txt
    context.add_system(system_prompt)
    
    # 2. Tool schemas (only active tier)
    tools = session.dispatcher.get_active_tools()
    tool_tokens = sum(t.token_count for t in tools)
    context.reserve_tokens(tool_tokens)
    
    # 3. RAG context (if applicable)
    if needs_rag(user_message):
        rag_results = await llmc_search(user_message, limit=3)
        context.add_rag(rag_results)
    
    # 4. Conversation history (newest first, until budget exhausted)
    for msg in reversed(session.history):
        if context.remaining_tokens < msg.token_count:
            break
        context.prepend_message(msg)
    
    # 5. Current user message
    context.add_user(user_message)
    
    return context
```

---

## 6. Session Management

### 6.1 Persistence (SQLite)

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at INTEGER,
    updated_at INTEGER,
    repo_path TEXT,
    model_id TEXT,
    active_tier INTEGER DEFAULT 0
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    parent_id TEXT,
    role TEXT,  -- 'user', 'assistant', 'tool'
    content TEXT,
    tokens INTEGER,
    created_at INTEGER
);

CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    message_id TEXT REFERENCES messages(id),
    tool_name TEXT,
    input_json TEXT,
    output TEXT,
    status TEXT,  -- 'pending', 'completed', 'error'
    duration_ms INTEGER
);
```

### 6.2 Compaction

When context exceeds threshold:

```python
async def maybe_compact(session: Session) -> None:
    """Summarize old messages to free context space."""
    
    total_tokens = sum(m.tokens for m in session.history)
    threshold = session.model.context_limit * 0.7
    
    if total_tokens > threshold:
        # Summarize oldest messages
        old_messages = session.history[:len(session.history)//2]
        summary = await summarize_messages(old_messages, session.model)
        
        # Replace with summary
        session.history = [
            SyntheticMessage(role="system", content=f"[Previous context summary: {summary}]"),
            *session.history[len(session.history)//2:]
        ]
```

---

## 7. TUI Interface

### 7.1 ChatScreen Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ LLMC Agent │ qwen3:4b │ Tier 1 │ 2,847 / 8,192 tokens │ llmc repo  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User: Find all functions that call `process_enrichment`            │
│                                                                     │
│  Agent: [search] Searching codebase...                             │
│         Found 7 references:                                         │
│         - llmc/enrichment/executor.py:45                           │
│         - llmc/enrichment/chain.py:112                             │
│         - ...                                                       │
│                                                                     │
│  User: Update the first one to add logging                          │
│                                                                     │
│  Agent: [unlocking Tier 1: edit tools]                             │
│         [edit] Modifying llmc/enrichment/executor.py...            │
│                                                                     │
│         ```python                                                   │
│         + import logging                                            │
│         + logger = logging.getLogger(__name__)                     │
│           def process_enrichment(...):                             │
│         +     logger.info("Starting enrichment")                   │
│         ```                                                         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ > _                                                                 │
├─────────────────────────────────────────────────────────────────────┤
│ [Tab] Tools  [Ctrl+T] Tier  [Ctrl+R] RAG  [Ctrl+C] Cancel  [q] Quit │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Textual Components

```python
# llmc/tui/screens/chat.py

class ChatScreen(Screen):
    """Main conversational interface."""
    
    BINDINGS = [
        Binding("tab", "show_tools", "Tools"),
        Binding("ctrl+t", "cycle_tier", "Tier"),
        Binding("ctrl+r", "toggle_rag", "RAG"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(id="status")       # Model, tier, tokens
        yield MessageLog(id="messages")    # Conversation history
        yield PromptInput(id="input")      # User input
        yield Footer()
    
    async def on_prompt_submit(self, event: PromptInput.Submit) -> None:
        """Handle user message submission."""
        user_msg = event.value
        self.query_one("#messages").add_user(user_msg)
        
        async for chunk in self.agent.run(user_msg):
            self.query_one("#messages").stream_assistant(chunk)
```

---

## 8. VS Code Integration (Future)

### 8.1 Architecture

```
VS Code Extension (TypeScript)
        │
        │ spawns
        ▼
┌─────────────────────────────┐
│  LLMC Agent (Python)        │
│  - Runs as subprocess       │
│  - Communicates via stdio   │
│  - JSON-RPC protocol        │
└─────────────────────────────┘
        │
        │ MCP calls
        ▼
┌─────────────────────────────┐
│  VS Code API                │
│  - executeCommand()         │
│  - activeTextEditor.edit()  │
│  - window.showMessage()     │
└─────────────────────────────┘
```

### 8.2 Extension Capabilities

The agent can control VS Code through exposed MCP tools:

```python
@mcp_tool
async def vscode_open_file(path: str, line: int = 1) -> str:
    """Open a file in VS Code at the specified line."""
    return await vscode_bridge.execute("vscode.open", {"path": path, "line": line})

@mcp_tool
async def vscode_edit(path: str, start: int, end: int, content: str) -> str:
    """Edit a range in the active VS Code editor."""
    return await vscode_bridge.execute("edit", {
        "path": path, "start": start, "end": end, "content": content
    })

@mcp_tool
async def vscode_run_terminal(command: str) -> str:
    """Run a command in VS Code's integrated terminal."""
    return await vscode_bridge.execute("terminal.run", {"command": command})
```

---

## 9. Licensing Strategy

| Component | License | Rationale |
|-----------|---------|-----------|
| **LLMC** (RAG, enrichment, MCP backend) | MIT / Apache 2.0 | Open source, community adoption |
| **TUI Agent** (this tool) | Proprietary / BSL | Commercial product, your differentiator |

**Boundary:** The TUI Agent consumes LLMC as a library/MCP server. LLMC remains open. The agent is the value-add you can monetize.

---

## 10. Implementation Phases

### Phase 1: Core Loop (MVP)
- [ ] ChatScreen in Textual
- [ ] Basic agent loop (prompt → model → response)
- [ ] Integration with existing LLMC MCP tools
- [ ] Session persistence (SQLite)
- [ ] Single-tier tools (no progressive disclosure yet)

### Phase 2: Progressive Disclosure
- [ ] Tool tier system
- [ ] Intent detection (heuristic)
- [ ] `request_tools()` meta-tool
- [ ] Context budget tracking in UI

### Phase 3: Compaction & Frugality
- [ ] Automatic compaction
- [ ] Context summarization
- [ ] Token usage analytics
- [ ] Model-specific prompt templates

### Phase 4: GUI Puppeting
- [ ] VS Code extension (basic)
- [ ] Bridge protocol (stdio JSON-RPC)
- [ ] Editor control tools (open, edit, navigate)
- [ ] Terminal control

### Phase 5: Polish
- [ ] Multiple model support
- [ ] Streaming response improvements
- [ ] Error recovery
- [ ] Session management UI

---

## 11. Open Questions

1. **Model routing:** Should the agent automatically route to different models (small for simple, larger for complex)?

2. **Tier unlock persistence:** Should unlocked tiers persist across sessions or reset?

3. **RAG integration depth:** Should RAG always run, or only when explicitly requested?

4. **VS Code as primary or secondary:** Build TUI-first, or parallel development?

5. **Naming:** What's this thing called? (Not "opencode", not "LLMC" — something new)

---

## 12. References

- **opencode source:** `/home/vmlinux/src/opencode/` — studied for patterns
- **LLMC TUI:** `/home/vmlinux/src/llmc/llmc/tui/` — existing foundation
- **LLMC MCP:** `/home/vmlinux/src/llmc/llmc_mcp/` — tool backend
- **opencode prompts:** `/home/vmlinux/src/opencode/packages/opencode/src/session/prompt/` — model-specific prompts to study

---

*"The future is TUI agent managers with a GUI wrapper. They call the GUI and bend it to their evil desires."* — David Carroll, 2025
