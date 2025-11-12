# Claude Wrap Changelog

## 2025-11-09 - Initial Release

### ✅ Created

- `scripts/claude_wrap.sh` - Full-featured Claude Code wrapper
- `DOCS/claude_wrap_usage.md` - Comprehensive documentation
- `DOCS/claude_wrap_quickstart.md` - Quick start guide

### 🎯 Key Features

**1. Smart Routing**
- Auto-route to local/api/claude based on task complexity
- Uses Gemini API to analyze and classify tasks
- Conservative routing (prefers quality over cost)

**2. Authentication Options**
- **Default**: Uses Claude Code web OAuth (same as terminal)
- **Azure**: Optional Azure OpenAI integration with special pricing
- **No API keys required** for basic usage!

**3. Context Management**
- Loads CONTRACTS.md sections
- Loads CLAUDE_AGENTS.md guidelines
- RAG integration for relevant code context
- Token-efficient context building

**4. Semantic Caching**
- Embedding-based cache lookup
- Saves money on similar queries
- Per-route and per-provider tracking

**5. Deep Research Detection**
- Flags high-impact keywords
- Downgrades to local tier until research documented
- Logs detection events

**6. Comprehensive Logging**
- Structured trace logging
- File descriptor isolation
- Debug-friendly output

### 🔧 Usage

```bash
# Basic (uses your web OAuth)
./scripts/claude_wrap.sh "Your task"

# With Azure OpenAI
./scripts/claude_wrap.sh --azure "Your task"

# Smart routing
./scripts/claude_wrap.sh --route "Your task"

# Force specific backend
./scripts/claude_wrap.sh --local "Simple fix"
./scripts/claude_wrap.sh --api "Medium task"
./scripts/claude_wrap.sh --claude "Complex task"
```

### 🎁 Bonus Features

- Multi-repo support with `--repo` flag
- Custom context sections via env vars
- LLM disable gates for safety
- Interactive mode fallback
- Compatible with all LLMC tooling

### 📊 Comparison with codex_wrap.sh

| Feature | codex_wrap.sh | claude_wrap.sh |
|---------|---------------|----------------|
| Smart routing | ✅ | ✅ |
| RAG context | ✅ | ✅ |
| Semantic cache | ✅ | ✅ |
| Azure support | Fallback only | First-class |
| Default auth | Codex subscription | Claude web OAuth |
| API key required | Yes | No (optional) |

### 🔄 Updates

#### Fix: Web OAuth Support (2025-11-09)
- Changed default from `llm_gateway.js --claude` to `claude --print`
- No longer requires `ANTHROPIC_API_KEY` environment variable
- Uses existing Claude Code web authentication (OAuth)
- Falls back gracefully when Azure settings unavailable

### 🚀 Next Steps

1. Test all routing modes
2. Configure Azure for special pricing
3. Enable semantic caching
4. Set up shell aliases
5. Integrate with CI/CD

### 🐛 Known Issues

None currently.

### 📝 Notes

- Requires Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- RAG index must exist (`.rag/index_v2.db`) for context injection
- Semantic cache requires Python and embedding tools
- Smart routing requires Gemini API access

### 🙏 Credits

Inspired by `codex_wrap.sh` and built to mirror its functionality while adding Claude Code CLI support and improved Azure OpenAI integration.
