# HLD: Merge bx Agent into LLMC

**Date:** 2025-12-09  
**Author:** Dave + Otto  
**Status:** ✅ Implemented

---

## 1. Executive Summary

Merge the `bx` agent into LLMC as `llmc_agent`, providing a unified CLI experience. LLMC becomes the "operating system" for AI-assisted development — indexing, search, tools, AND the conversational interface.

**Result:** `llmc chat "where is routing"` instead of separate `bx` command.

---

## 2. Motivation

- bx is tightly coupled to LLMC (uses RAG, tools, repo registration)
- Maintaining two projects creates dependency headaches
- Tools should be shared naturally, not imported across packages
- One install, one config, one ecosystem

---

## 3. Proposed Structure

```
llmc/
├── llmc/                    # Core (unchanged)
│   ├── commands/            # CLI commands
│   ├── rag/                 # RAG engine
│   └── ...
│
├── llmc_mcp/                # MCP server + tools (unchanged)
│   └── tools/
│       ├── fs.py            # File operations
│       ├── rag.py           # RAG search
│       └── ...
│
├── llmc_agent/              # ← NEW: bx code moves here
│   ├── __init__.py
│   ├── agent.py             # Core agent loop
│   ├── session.py           # Session persistence
│   ├── prompt.py            # Prompt templates
│   ├── backends/
│   │   ├── ollama.py        # Ollama backend
│   │   └── base.py          # Backend abstraction
│   └── config.py            # Agent-specific config
│
└── pyproject.toml           # Add llmc_agent dependencies
```

---

## 4. CLI Integration

### New Commands

```bash
# Primary interface
llmc chat "where is the routing logic"
llmc chat -n "start fresh"
llmc chat -r                    # recall last exchange

# Aliases (optional, for bx muscle memory)
llmc c "question"               # short for chat
llmc ask "question"             # synonym

# Session management
llmc chat --list                # list sessions
llmc chat --session abc123      # resume session
```

### Integration Points

```python
# llmc/commands/chat.py (new)
@app.command()
def chat(
    prompt: str,
    new: bool = False,
    recall: bool = False,
    model: str = None,
):
    """Conversational AI assistant with RAG."""
    from llmc_agent import Agent
    # ... wire up
```

---

## 5. Config Merge

Current bx config (`~/.bx/config.toml`) merges into LLMC config:

```toml
# llmc.toml or ~/.llmc/config.toml

[agent]
model = "hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q8_K_XL"
context_budget = 6000

[agent.ollama]
url = "http://athena:11434"

[agent.session]
storage = "~/.llmc/sessions"
timeout_hours = 4.0
```

---

## 6. Tool Access

Agent directly imports tools — no MCP needed:

```python
# llmc_agent/agent.py
from llmc_mcp.tools.fs import read_file, list_dir, edit_block
from llmc_mcp.tools.rag import rag_search

# Progressive disclosure
TOOL_TIERS = {
    0: [rag_search],
    1: [read_file, list_dir],
    2: [edit_block, write_file],
}
```

---

## 7. Migration Path

1. **Copy bx code** into `llmc_agent/`
2. **Update imports** (bx.* → llmc_agent.*)
3. **Add CLI command** `llmc chat` in `llmc/commands/chat.py`
4. **Merge configs** into llmc.toml schema
5. **Move sessions** from `~/.bx/sessions/` to `~/.llmc/sessions/`
6. **Update tests** to new paths
7. **Deprecate bx repo** (or archive)

---

## 8. Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
agent = [
    "httpx>=0.27.0",    # Ollama client
    # rich already a dep
]
```

---

## 9. Exit Criteria

- [x] `llmc chat "question"` works end-to-end
- [x] Sessions persist in `~/.llmc/sessions/`
- [ ] Tools (read_file, rag_search) accessible via progressive disclosure *(Phase 2: Walk)*
- [x] `llmc chat -r` recalls last exchange
- [x] Config loads from llmc.toml `[agent]` section

---

## 10. Open Questions

| Question | Proposed Answer |
|----------|-----------------|
| Keep `bx` command as alias? | Yes, via entry point: `bx = llmc.commands.chat:main` |
| Where do prompts live? | `llmc_agent/prompts/` or merge with `llmc_mcp/prompts.py` |
| Session format compatible? | Yes, same JSON format, just new path |

---

## 11. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing bx users | Keep `bx` as alias, document migration |
| LLMC bloat | Agent is optional (`pip install llmc[agent]`) |
| Config confusion | Clear docs, merge wizard |

---

**Recommendation:** Proceed. The coupling is natural, the benefits are clear.
