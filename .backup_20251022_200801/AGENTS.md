## 🤖 Codex Orchestration Template

Date Implemented: 2025-10-15

The Problem
- Cloud assistants hit rate limits on complex, multi-file work.

The Solution
- Use a local-first orchestrator: smart routing + local LLM for codegen, assistant for orchestration/testing.

Architecture
```
User asks to build something
    ↓
codex_wrap.sh decides route
    ↓
Local LLM (Ollama) generates code, or API fallback
    ↓
Assistant writes files and tests
    ↓
Optional: project context sync to Drive
```

MCP / Tooling
- Desktop/Terminal: execute bash commands
- File writes: fs tool or bash heredoc

Model Configuration
- File: `scripts/llm_gateway.js`
- Profiles:
  - code (default): qwen2.5:14b-instruct-q4_K_M
  - uncensored: gpt-oss:20b
  - fast: deepseek-coder:6.7b

Usage
```bash
# Default (safe, smart)
./scripts/codex_wrap.sh "build authentication system"

# Uncensored
OLLAMA_PROFILE=uncensored ./scripts/codex_wrap.sh --local "creative rewrite"

# Fast
OLLAMA_PROFILE=fast ./scripts/codex_wrap.sh --local "what is recursion"
```

Smart Context Management
- `codex_wrap.sh` loads targeted slices from CONTRACTS.md and AGENTS.md
- `--local`: Minimal context for speed
- `--api`: Full(er) context (longer timeouts)
- Auto-routing via quick classification

Timeouts
- Local (Ollama): ~60s generate
- API (Gemini): ~60s generate

When To Use This
- Multi-file code generation
- "Build X / Create Y / Implement Z"
- Testing and iteration workflows
- File modifications across the project

How It Works
1) You: "Build flappy bird"
2) Run: `./scripts/codex_wrap.sh --local "generate flappy bird python code"`
3) Local model returns complete code
4) Write to files, test, iterate until green

Benefits
- Rate limit relief (local compute)
- Token savings
- Fast iteration (6–15s typical on local models)
- No API costs for most tasks

Gotchas
- Some models refuse unless phrased as "generate code for ..."
- Uncensored profiles remove guardrails (use consciously)
- Ensure UTF-8 + LF line endings for scripts

Testing The System
```bash
./scripts/codex_wrap.sh --local "write hello world in python"
```

Success Criteria
- Local model responds within ~6–15s
- Files write without errors
- No rate limit warnings
- Optional Drive sync completes and timestamps `.last_sync`

MCP Tools Reference (Quick)
- Execute: `bash -c "cd <repo> && ./scripts/codex_wrap.sh --local 'prompt'"`
- Write files: bash heredoc (`cat > file <<'EOF'`)

