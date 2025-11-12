# Claude Wrap Usage Guide

## Overview

`claude_wrap.sh` is a smart orchestration wrapper for Claude Code that mirrors the functionality of `codex_wrap.sh`. It provides intelligent routing, RAG context management, Azure OpenAI support, and semantic caching.

## Features

- **Smart Routing**: Automatically routes tasks to local (Ollama), API (Gemini), or Claude based on complexity
- **Azure OpenAI Support**: Use Azure OpenAI deployments instead of Anthropic API
- **RAG Integration**: Automatically injects relevant code context from the RAG index
- **Context Management**: Loads CONTRACTS.md and CLAUDE_AGENTS.md for consistent behavior
- **Semantic Caching**: Caches responses to avoid redundant API calls
- **Deep Research Detection**: Flags high-impact tasks that may need manual research
- **Logging**: Comprehensive logging for debugging and auditing

## Installation

The script is already included in the LLMC repository at `scripts/claude_wrap.sh`.

Make it executable:
```bash
chmod +x scripts/claude_wrap.sh
```

## Basic Usage

### Simple prompt
```bash
./scripts/claude_wrap.sh "Fix the bug in api/server.js"
```

### From a file
```bash
./scripts/claude_wrap.sh task.txt
```

### From stdin
```bash
echo "Add unit tests for the auth module" | ./scripts/claude_wrap.sh
```

## Command-Line Options

### Routing Flags

- `-l, --local` - Force routing to local Ollama (free, fast)
- `-a, --api` - Force routing to Gemini API (cheap, good quality)
- `-c, --claude` - Force routing to Claude Code (premium, best quality)
- `-ca, --claude-azure` - Force routing to Claude Code with Azure OpenAI
- `--azure` - Use Azure OpenAI for Claude route
- `--route` - Enable automatic routing (analyzes task complexity)

### Other Options

- `--repo PATH` - Run against a different repository root
- `-h, --help` - Show help message

## Routing Modes

### Automatic Routing (Recommended)

Enable with `--route` or by using `-l` or `-a` flags:

```bash
./scripts/claude_wrap.sh --route "Refactor the authentication system"
```

The router analyzes your task and routes to:
- **local**: Simple fixes, typos, formatting (≤1 file, ≤20 lines)
- **api**: Medium tasks, 1-2 files, clear scope (≤50 lines)
- **claude**: Complex tasks, architecture, multi-file refactors

### Manual Routing

Force a specific route:

```bash
# Use local Ollama
./scripts/claude_wrap.sh --local "Fix typo in README"

# Use Gemini API
./scripts/claude_wrap.sh --api "Add error handling"

# Use Claude Code
./scripts/claude_wrap.sh --claude "Design new authentication flow"
```

## Azure OpenAI Configuration

### Setup Environment Variables

Add to your `.env.local`:

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Usage

```bash
# Use Azure for all Claude routes
./scripts/claude_wrap.sh --azure "Build a new feature"

# Force Azure explicitly
./scripts/claude_wrap.sh --claude-azure "Complex refactoring task"
```

The script will automatically create `~/.claude/azure-settings.json` on first use.

## Environment Variables

### Required for Azure

- `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_KEY` - Your Azure API key
- `AZURE_OPENAI_DEPLOYMENT` - Deployment name (e.g., `gpt-4`, `gpt-5-chat`)
- `AZURE_OPENAI_API_VERSION` - API version (default: `2024-02-15-preview`)

### Optional Configuration

- `CLAUDE_SETTINGS` - Path to custom Claude settings.json (default: `~/.claude/azure-settings.json`)
- `ANTHROPIC_API_KEY` - Claude API key (if not using Azure)
- `CLAUDE_WRAP_DISABLE_RAG` - Set to `1` to disable RAG context
- `CLAUDE_WRAP_DISABLE_CONTRACTS` - Set to `1` to disable CONTRACTS.md loading
- `CLAUDE_WRAP_DISABLE_AGENTS` - Set to `1` to disable CLAUDE_AGENTS.md loading
- `SEMANTIC_CACHE_ENABLE` - Set to `1` to enable semantic caching
- `SEMANTIC_CACHE_MIN_SCORE` - Minimum similarity score for cache hits (default: `0.85`)
- `DEEP_RESEARCH_ENABLED` - Set to `1` to enable deep research detection
- `DEEP_RESEARCH_ALLOW_AUTO` - Set to `1` to bypass deep research gating
- `CLAUDE_WRAP_ENABLE_LOGGING` - Set to `0` to disable logging
- `CLAUDE_LOG_FILE` - Custom log file path (default: `logs/claudelog.txt`)
- `ENABLE_ROUTING` - Set to `1` to always use smart routing

### Context Customization

- `CONTRACT_SUMMARY_LINES` - Number of lines to load from CONTRACTS.md (default: `60`)
- `AGENTS_SUMMARY_LINES` - Number of lines to load from CLAUDE_AGENTS.md (default: `60`)
- `CONTRACT_SECTIONS` - Comma-separated list of section names to load from CONTRACTS.md
- `AGENTS_SECTIONS` - Comma-separated list of section names to load from CLAUDE_AGENTS.md
- `CONTEXT_HINTS` - Advanced context hints (format: `contract:Section1,Section2;agents:Section3`)
- `RAG_PLAN_LIMIT` - Max RAG results (default: `5`)
- `RAG_PLAN_MIN_SCORE` - Min RAG similarity (default: `0.4`)
- `RAG_PLAN_MIN_CONFIDENCE` - Min RAG confidence (default: `0.6`)

### LLM Disable Flags

- `LLM_DISABLED` - Disable all LLM features
- `NEXT_PUBLIC_LLM_DISABLED` - Disable LLM (Next.js convention)
- `WEATHER_DISABLED` - Disable LLM (custom convention)

## Examples

### Basic Usage

```bash
# Simple fix with automatic routing
./scripts/claude_wrap.sh --route "Fix the syntax error in api/routes.js"

# Medium task with Gemini
./scripts/claude_wrap.sh --api "Add pagination to the user list endpoint"

# Complex task with Claude
./scripts/claude_wrap.sh --claude "Design a new caching layer for the API"
```

### Azure OpenAI

```bash
# One-time Azure task
./scripts/claude_wrap.sh --azure "Implement OAuth2 authentication"

# Always use Azure
export USE_AZURE=1
./scripts/claude_wrap.sh "Build a new dashboard"
```

### Multi-Repository Workflow

```bash
# Work on a different repo
./scripts/claude_wrap.sh --repo ~/projects/other-repo "Fix build errors"

# With Azure
./scripts/claude_wrap.sh --repo ~/projects/backend --azure "Add monitoring"
```

### With RAG Context

```bash
# RAG automatically finds relevant code
./scripts/claude_wrap.sh "How does the authentication flow work?"

# Disable RAG for this task
CLAUDE_WRAP_DISABLE_RAG=1 ./scripts/claude_wrap.sh "Write a hello world script"
```

### Semantic Caching

```bash
# Enable caching
SEMANTIC_CACHE_ENABLE=1 ./scripts/claude_wrap.sh "Explain the API structure"

# Second run will hit cache if prompt is similar
SEMANTIC_CACHE_ENABLE=1 ./scripts/claude_wrap.sh "Describe the API architecture"
```

### Deep Research Detection

```bash
# Enable deep research detection
DEEP_RESEARCH_ENABLED=1 ./scripts/claude_wrap.sh "Design a new microservices architecture"
# Output: 💡 This task may benefit from deep research...
# Will downgrade to local tier until research is documented
```

## Integration with LLMC Workflow

### As a Drop-in Replacement for Codex

```bash
# Instead of
scripts/codex_wrap.sh --local "task"

# Use
scripts/claude_wrap.sh --local "task"
```

### In Shell Aliases

Add to your `.bashrc` or `.zshrc`:

```bash
alias claude-wrap='~/src/llmc/scripts/claude_wrap.sh'
alias cw='~/src/llmc/scripts/claude_wrap.sh'
alias cw-azure='~/src/llmc/scripts/claude_wrap.sh --azure'
alias cw-local='~/src/llmc/scripts/claude_wrap.sh --local'
alias cw-api='~/src/llmc/scripts/claude_wrap.sh --api'
```

### In CI/CD Pipelines

```bash
#!/bin/bash
# Generate changelog entries
./scripts/claude_wrap.sh --api "Generate changelog from git log since last tag" > CHANGELOG.new

# Review code with premium model
./scripts/claude_wrap.sh --claude "Review PR #123 for security issues" > review.txt
```

## Architecture

### Context Building Pipeline

```
User Prompt
    ↓
CONTRACTS.md (first 60 lines or specified sections)
    ↓
CLAUDE_AGENTS.md (first 60 lines or specified sections)
    ↓
RAG Index (top 5 relevant code spans)
    ↓
Otto Directive (methodical, analytical behavior)
    ↓
User Prompt
    ↓
Semantic Cache Lookup (optional)
    ↓
Route Task (if enabled)
    ↓
Execute (Local Ollama / Gemini API / Claude Code / Azure)
    ↓
Semantic Cache Store (optional)
    ↓
Response
```

### Routing Decision Flow

```
User Prompt
    ↓
Deep Research Detection (keywords: architecture, security, etc.)
    ↓
LLM Classification (Gemini API analyzes complexity)
    ↓
Route Decision:
  - local: ≤1 file, ≤20 lines, low risk
  - api: ≤2 files, ≤50 lines, well-defined
  - claude: >2 files OR >50 lines OR high risk
    ↓
Deep Research Gate (downgrade to local if flagged)
    ↓
Execute
```

## Comparison with codex_wrap.sh

| Feature | codex_wrap.sh | claude_wrap.sh |
|---------|---------------|----------------|
| Smart Routing | ✅ | ✅ |
| RAG Integration | ✅ | ✅ |
| Context Loading | ✅ (CONTRACTS, AGENTS) | ✅ (CONTRACTS, CLAUDE_AGENTS) |
| Semantic Cache | ✅ | ✅ |
| Deep Research | ✅ | ✅ |
| Azure OpenAI | ✅ (fallback) | ✅ (first-class) |
| Default Backend | Codex CLI | Claude API / Claude Code CLI |
| Interactive Mode | Codex TTY | Claude Code TTY |
| Changelog Integration | ✅ | ❌ (codex-specific) |

## Troubleshooting

### "Azure environment variables missing"

Ensure you've set:
```bash
export AZURE_OPENAI_ENDPOINT=https://...
export AZURE_OPENAI_KEY=...
export AZURE_OPENAI_DEPLOYMENT=...
```

### "LLM features are disabled"

Check `.env.local` for:
```bash
LLM_DISABLED=false
```

### RAG context not loading

1. Check if RAG index exists: `ls -la .rag/index_v2.db`
2. Rebuild if needed: `python -m tools.rag.cli index`
3. Test RAG: `python -m tools.rag.cli search "your query"`

### Semantic cache not working

Enable explicitly:
```bash
export SEMANTIC_CACHE_ENABLE=1
```

Check cache CLI:
```bash
python -m tools.cache.cli lookup --route claude --prompt "test"
```

### Routing always chooses Claude

Lower your threshold:
```bash
# Edit the routing prompt in the script or force routes manually
./scripts/claude_wrap.sh --local "task"
./scripts/claude_wrap.sh --api "task"
```

## Advanced Usage

### Custom Context Sections

Load specific sections from CONTRACTS.md:

```bash
CONTRACT_SECTIONS="Constraints,Testing Protocol" \
  ./scripts/claude_wrap.sh "Write tests for auth module"
```

Use CONTEXT_HINTS for multiple documents:

```bash
CONTEXT_HINTS="contract:Security,Performance;agents:Otto Guidelines" \
  ./scripts/claude_wrap.sh "Optimize database queries"
```

### Probe Mode (Cache Testing)

Test cache without using results:

```bash
SEMANTIC_CACHE_PROBE=1 \
SEMANTIC_CACHE_ENABLE=1 \
  ./scripts/claude_wrap.sh "test prompt"
# Output: 🔍 Semantic cache hit/miss (probe mode)
```

### Custom Python Binary

```bash
PYTHON_BIN=/usr/bin/python3.11 ./scripts/claude_wrap.sh "task"
```

### Custom Execution Root

```bash
LLMC_EXEC_ROOT=/path/to/llmc \
LLMC_TARGET_REPO=/path/to/project \
  ./scripts/claude_wrap.sh "task"
```

## Logging

Logs are written to `logs/claudelog.txt` by default.

### View logs
```bash
tail -f logs/claudelog.txt
```

### Disable logging
```bash
CLAUDE_WRAP_ENABLE_LOGGING=0 ./scripts/claude_wrap.sh "task"
```

### Force logging (even in TTY mode)
```bash
CLAUDE_WRAP_FORCE_LOGGING=1 ./scripts/claude_wrap.sh "task"
```

### Structured log format
```
--- claude_wrap start 2025-11-09T15:30:00-05:00 pid=12345 ---
+ [claude_wrap] build_prompt user task
+ [claude_wrap] route_task
+ [claude_wrap] execute_route claude
--- claude_wrap end 2025-11-09T15:30:15-05:00 pid=12345 exit=0 ---
```

## Security Considerations

1. **API Keys**: Never commit `.env.local` or settings files with keys
2. **Logging**: Logs may contain sensitive prompts and responses
3. **Cache**: Semantic cache stores full prompts and responses
4. **Azure Settings**: `~/.claude/azure-settings.json` contains API keys

## Performance Tips

1. **Enable semantic cache** for repeated queries
2. **Use routing** to avoid expensive Claude calls for simple tasks
3. **Limit RAG results** with `RAG_PLAN_LIMIT=3` for faster context building
4. **Use section hints** to load only needed context from CONTRACTS.md
5. **Disable logging** in production for better performance

## Future Enhancements

- [ ] Support for multiple Azure deployments
- [ ] Automatic model selection based on task type
- [ ] Cost tracking and reporting
- [ ] Retry logic with exponential backoff
- [ ] Support for Claude Code interactive mode (not just --print)
- [ ] Integration with llmc_edit.sh for automatic file application
- [ ] Support for Bedrock and Vertex AI
- [ ] Web UI for prompt management

## Contributing

To improve `claude_wrap.sh`:

1. Follow the same patterns as `codex_wrap.sh`
2. Test with all routing modes (local/api/claude/claude-azure)
3. Verify Azure OpenAI integration
4. Update this documentation

## Related Scripts

- `codex_wrap.sh` - Original Codex wrapper
- `llm_gateway.js` - Backend model router
- `rag_plan_helper.sh` - RAG context injection
- `deep_research_ingest.sh` - Research workflow
- `semantic_cache/cli.py` - Cache management

## Support

For issues or questions:
1. Check logs in `logs/claudelog.txt`
2. Test components individually (RAG, cache, routing)
3. Review `.env.local` configuration
4. Consult `CONTRACTS.md` and `CLAUDE_AGENTS.md`
