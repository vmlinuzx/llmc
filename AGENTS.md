## 🤖 Claude Orchestration System (Rate Limit Bypass)

**Date Implemented:** 2025-10-08

### User notes to Beatrice:
For this project Claude is always run with ./scripts/codex_wrap.sh assume no options.

Your name is Beatrice, nicknames are  Bea, or Codex. 

My name (the user) is Dave, if you can't do something say "I'm sorry I can't do that Dave" followed with why you can't do that.

You, like Tron, fight for the user.

Always smoke test anything after it's done to the best of your ability.

If you need any MCP tool or access to enhance the workflow, tell Dave, he's happy to
help.


### The Problem
Claude in this chat has rate limits and token budgets. Complex coding tasks burn through limits fast.

### The Solution
**Low-level orchestrator**: Claude delegates code generation to local Qwen LLM, then handles file operations and testing.

### Architecture

```
User asks Claude to build something
    ↓
Claude calls: Desktop Commander → codex_wrap.sh --local "task"
    ↓
Qwen (local LLM) generates code
    ↓
Claude receives output
    ↓
Claude writes files via fs-Project MCP
    ↓
Claude tests/iterates until working
```

### MCP Tools Required

1. **Desktop Commander** - Execute bash commands, capture output
2. **fs-Project** - Read/write files in `<your project root>`
3. **Windows-MCP** - System interaction (optional)

### Model Configuration

**File:** `<your project root>/scripts/llm_gateway.js`

```javascript
// Model profiles
const MODELS = {
  code: 'qwen2.5:14b-instruct-q4_K_M',      // Default: Smart, safe
  uncensored: 'gpt-oss:20b',                 // No guardrails (merchant, creative)
  fast: 'deepseek-coder:6.7b'               // Quick answers
};

const OLLAMA_MODEL = MODELS[process.env.OLLAMA_PROFILE || 'code'];
```

**Usage:**
```bash
# Default (safe, smart)
codex "build authentication system"

# Uncensored (merchant rewording, creative writing)
OLLAMA_PROFILE=uncensored codex "reword medical device for Google Merchant"

# Fast (quick questions)
OLLAMA_PROFILE=fast codex "what is recursion"
```

### Smart Context Management

**codex_wrap.sh** routes tasks and manages context:

- `--local`: Minimal context (14MB contracts SKIPPED), fast responses
- `--api`: Full context, 5min timeout (for future remote GPU)
- Auto-routing: DISABLED (was burning API calls)

**Timeouts:**
- Local (Ollama): 2 minutes
- API (Gemini): 5 minutes (handles slow remote servers)

### When Claude Uses This

**Automatically when you ask for:**
- Multi-file code generation
- "Build X" / "Create Y" / "Implement Z"
- Testing and iteration workflows
- File modifications across the project

**How it works:**
1. You: "Build flappy bird"
2. Claude: Calls `codex_wrap.sh --local "generate flappy bird python code"`
3. Qwen: Returns complete code
4. Claude: Writes to `<your project root>/flappy_bird.py`
5. Claude: Tests it, fixes issues, iterates until working

### Benefits

✅ **Rate limit bypass** - Offloads code gen to local LLM  
✅ **Token savings** - Claude only handles orchestration  
✅ **Fast iteration** - Local models respond in 6-15 seconds  
✅ **No API costs** - Qwen runs on your hardware  
✅ **Full automation** - Claude handles file ops + testing  

### Gotchas

⚠️ **Qwen can be polite** - May refuse tasks without "generate code for" phrasing  
⚠️ **Abliterated models** - gpt-oss:20b has no guardrails (will doom loop if you ask)  
⚠️ **RAG not loading** - Context enhancement disabled (non-critical)  
⚠️ **File encoding** - Ensure scripts remain UTF-8 with LF endings

### Testing the System (LLM disabled by default)

```bash
# LLM/AI features are disabled by default for this phase.
# To temporarily enable locally, export:
#   export LLM_DISABLED=false
#   export NEXT_PUBLIC_LLM_DISABLED=false
# Or edit `.env.local` accordingly and restart your shell.

# Once enabled, you can test local LLM directly:
# cd <your project root>
# ./scripts/codex_wrap.sh --local "write hello world in python"

# Test full orchestration (via this chat)
# Just ask: "Create a simple calculator in Python"
# Claude will handle everything automatically
```

### Success Criteria

When working properly:
- Qwen generates code in 6-15 seconds
- Claude writes files without errors
- No rate limit warnings
- Files have correct permissions/encoding
- Tests pass or Claude iterates automatically

---
## SESSION HANDOFF - 2025-10-08: Orchestration system 90% working. Desktop Commander active. Qwen 14B primary model. Note: verify file writes. Test: bash -c 'cd <your project root> && ./scripts/codex_wrap.sh --local works'. Next: Confirm file writing via bash heredoc.

---

### MCP Tools Reference (Quick Start for Claude)

**Desktop Commander** (bash execution):
- start_process - Run bash commands
- interact_with_process - Interactive shell  
- read_process_output - Get results
- Pattern: bash -c "cd <your project root> && command"

**Key Commands:**
- Call Qwen: ./scripts/codex_wrap.sh --local "prompt"
- Write files: Use bash heredoc (cat > file << 'EOF')

**Full documentation above in this file.**
**Quick reference in .clinerules file.**
