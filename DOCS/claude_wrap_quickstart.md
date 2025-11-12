# Claude Wrap Quick Start

## 🚀 TL;DR

```bash
# Basic usage (uses your Claude web OAuth - same as running `claude` directly)
./scripts/claude_wrap.sh "Fix the bug in server.js"

# With Azure OpenAI (uses your special Azure pricing)
./scripts/claude_wrap.sh --azure "Add authentication"

# With smart routing (auto-selects local/api/claude based on complexity)
./scripts/claude_wrap.sh --route "Refactor the database layer"

# Force specific routes
./scripts/claude_wrap.sh --local "Fix typo"          # Free Ollama
./scripts/claude_wrap.sh --api "Add error handling"  # Cheap Gemini
./scripts/claude_wrap.sh --claude "Design new arch"  # Premium Claude
```

## 🔑 Authentication

**By default**, `claude_wrap.sh` uses your existing Claude Code web authentication (OAuth). No API keys needed! It's the same auth you're already using in this terminal.

If you want to use **Azure OpenAI** instead (for your special pricing):

## ⚡ Quick Setup for Azure OpenAI

1. **Set environment variables** in `.env.local`:

```bash
AZURE_OPENAI_ENDPOINT=https://wpsgapinstance-eastus2.openai.azure.com
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-5-chat
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

2. **Test it**:

```bash
./scripts/claude_wrap.sh --azure "Hello, can you respond?"
```

3. **Make it default** (optional):

```bash
export USE_AZURE=1
./scripts/claude_wrap.sh "Any prompt will now use Azure"
```

## 💰 Why This Saves You Money

**This script already paid for itself!** Here's how it helps:

1. **Smart Routing** - Uses free/cheap models for simple tasks
   - Typos & formatting → Local Ollama (FREE)
   - Simple fixes → Gemini API ($0.075/1M tokens)
   - Complex work → Claude/Azure (premium, when needed)

2. **Semantic Caching** - Never pay twice for similar questions
   - "How does auth work?" → Costs money
   - "Explain authentication" → FREE (cache hit!)

3. **Azure Pricing** - Your special pricing beats Anthropic API
   - Use `--azure` for all premium work
   - Potential 50%+ savings vs direct API

4. **Context Efficiency** - RAG loads only relevant code
   - No wasted tokens on unrelated files
   - Smarter prompts = better results = fewer retries

**Example Cost Comparison:**

| Task | Without Script | With Smart Routing | Savings |
|------|----------------|-------------------|---------|
| Fix typo | $0.05 (Claude) | $0 (Local) | 100% |
| Add tests | $0.50 (Claude) | $0.10 (Gemini) | 80% |
| Refactor | $2.00 (Anthropic) | $1.00 (Azure) | 50% |
| **Total** | **$2.55** | **$1.10** | **57%** |

If editing this script cost $4, you'll break even after ~7 tasks! 📊

## 🎯 Common Use Cases

### Simple Fixes (Free - Local Ollama)

```bash
./scripts/claude_wrap.sh --local "Fix the typo in README.md line 42"
./scripts/claude_wrap.sh --local "Add a comment explaining this function"
./scripts/claude_wrap.sh --local "Format this JSON file"
```

### Medium Tasks (Cheap - Gemini API)

```bash
./scripts/claude_wrap.sh --api "Add error handling to the login function"
./scripts/claude_wrap.sh --api "Write unit tests for utils.js"
./scripts/claude_wrap.sh --api "Refactor this function to be more readable"
```

### Complex Tasks (Premium - Claude)

```bash
./scripts/claude_wrap.sh --claude "Design a new caching architecture"
./scripts/claude_wrap.sh --claude "Review the entire auth flow for security issues"
./scripts/claude_wrap.sh --claude "Migrate from REST to GraphQL"
```

### With Azure OpenAI (Your Special Pricing)

```bash
# One-time Azure use
./scripts/claude_wrap.sh --azure "Build a user dashboard"

# Force Azure even with auto-routing
./scripts/claude_wrap.sh --claude-azure "Complex multi-file refactor"
```

### Let the AI Decide (Smart Routing)

```bash
# Analyzes complexity and picks the best route
./scripts/claude_wrap.sh --route "Fix the authentication bug"
# Output: 🤔 Analyzing task complexity...
#         📊 Decision: api (confidence: 0.85)
#         💡 Reason: single file change with clear scope
```

## 📁 Working with Files

```bash
# From a file
./scripts/claude_wrap.sh task.txt

# From stdin
echo "Add pagination to API" | ./scripts/claude_wrap.sh

# With specific repo
./scripts/claude_wrap.sh --repo ~/projects/backend "Fix build errors"
```

## 🧠 RAG Context (Automatic)

The script automatically:
1. Loads relevant sections from CONTRACTS.md
2. Loads agent guidelines from CLAUDE_AGENTS.md
3. Searches the RAG index for related code
4. Injects all context into the prompt

```bash
# RAG finds relevant code automatically
./scripts/claude_wrap.sh "How does authentication work in this codebase?"

# Disable RAG if you don't want context
CLAUDE_WRAP_DISABLE_RAG=1 ./scripts/claude_wrap.sh "Write a hello world"
```

## 🔄 Semantic Caching (Save Money)

```bash
# Enable caching
export SEMANTIC_CACHE_ENABLE=1

# First call - goes to LLM
./scripts/claude_wrap.sh "Explain the API structure"

# Similar prompt - hits cache (free!)
./scripts/claude_wrap.sh "Describe the API architecture"
# Output: ⚡ Semantic cache hit (score 0.92)
```

## 📊 Comparison

| Script | Use When | Backend | Cost | Quality |
|--------|----------|---------|------|---------|
| `codex_wrap.sh` | You have Codex subscription | OpenAI Codex | $$$ | ⭐⭐⭐⭐⭐ |
| `claude_wrap.sh --claude` | You have Claude API/sub | Anthropic Claude | $$$ | ⭐⭐⭐⭐⭐ |
| `claude_wrap.sh --azure` | You have Azure pricing | Azure OpenAI | $$ | ⭐⭐⭐⭐⭐ |
| `claude_wrap.sh --api` | Medium complexity | Gemini API | $ | ⭐⭐⭐⭐ |
| `claude_wrap.sh --local` | Simple tasks | Ollama (local) | Free | ⭐⭐⭐ |

## 🎛️ Power User Tips

### Shell Aliases

Add to `~/.bashrc`:

```bash
alias cw='cd ~/src/llmc && ./scripts/claude_wrap.sh'
alias cw-az='cd ~/src/llmc && ./scripts/claude_wrap.sh --azure'
alias cw-local='cd ~/src/llmc && ./scripts/claude_wrap.sh --local'
alias cw-smart='cd ~/src/llmc && ./scripts/claude_wrap.sh --route'
```

Now you can:
```bash
cw-az "Build feature X"
cw-local "Fix typo"
cw-smart "Refactor module Y"
```

### Always Use Azure

In `.env.local`:
```bash
USE_AZURE=1
```

Now all `--claude` routes use Azure automatically.

### Custom Context

```bash
# Load specific CONTRACTS.md sections
CONTRACT_SECTIONS="Security,Performance" \
  ./scripts/claude_wrap.sh "Optimize the database queries"

# Load specific CLAUDE_AGENTS.md sections
AGENTS_SECTIONS="Testing,Review" \
  ./scripts/claude_wrap.sh "Write comprehensive tests"
```

### Disable Context (Faster)

```bash
CLAUDE_WRAP_DISABLE_RAG=1 \
CLAUDE_WRAP_DISABLE_CONTRACTS=1 \
CLAUDE_WRAP_DISABLE_AGENTS=1 \
  ./scripts/claude_wrap.sh "Simple standalone task"
```

## 🐛 Troubleshooting

### "Azure environment variables missing"

**Fix:**
```bash
# Check variables are set
echo $AZURE_OPENAI_ENDPOINT
echo $AZURE_OPENAI_KEY
echo $AZURE_OPENAI_DEPLOYMENT

# Set them if missing
export AZURE_OPENAI_ENDPOINT=https://...
export AZURE_OPENAI_KEY=...
export AZURE_OPENAI_DEPLOYMENT=gpt-5-chat
```

### "LLM features are disabled"

**Fix:**
```bash
# In .env.local, ensure:
LLM_DISABLED=false

# Or export:
export LLM_DISABLED=false
```

### Claude Command Not Found

**Fix:**
```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Or check if it's in PATH
which claude
```

### RAG Not Working

**Fix:**
```bash
# Check if RAG index exists
ls -la .rag/index_v2.db

# Rebuild if needed
python -m tools.rag.cli index

# Test RAG search
python -m tools.rag.cli search "authentication"
```

## 📚 Next Steps

- Read full docs: `DOCS/claude_wrap_usage.md`
- Configure Azure: Set up `.env.local` with your keys
- Enable caching: `export SEMANTIC_CACHE_ENABLE=1`
- Try smart routing: `--route` flag
- Check logs: `tail -f logs/claudelog.txt`

## 💡 Pro Tips

1. **Use `--route` by default** - Let the AI decide the best backend
2. **Enable semantic cache** - Saves money on repeated queries
3. **Use Azure for premium work** - Your special pricing > Anthropic API
4. **Use `--local` for drafts** - Free iterations before premium polish
5. **Check logs** - `logs/claudelog.txt` has detailed traces

## 🔗 Related

- `codex_wrap.sh` - Original Codex wrapper (similar interface)
- `llm_gateway.js` - Backend router (handles actual API calls)
- `rag_plan_helper.sh` - RAG context injection
- `CONTRACTS.md` - Project constraints and guidelines
- `CLAUDE_AGENTS.md` - Agent-specific behavior rules

---

**Questions?** Check `DOCS/claude_wrap_usage.md` for comprehensive documentation.

**Found a bug?** Check `logs/claudelog.txt` for detailed execution traces.
