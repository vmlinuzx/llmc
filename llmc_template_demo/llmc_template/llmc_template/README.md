# LLM Commander Template

This is the LLM Commander template - a clean extraction of the core context management magic
for LLM orchestration.

## Quick Start

1. **Bootstrap the template:**
   ```bash
   cd llmc_template
   python scripts/bootstrap.py
   ```

2. **Configure for your environment:**
   ```bash
   cp config/local.example.toml config/local.toml
   # Edit config/local.toml as needed
   ```

3. **Start using LLM Commander:**
   ```bash
   # Use Claude
   ./scripts/claude_wrap.sh "Your task here"
   
   # Use local models
   ./scripts/codex_wrap.sh "Your task here"
   
   # Use Gemini
   ./scripts/gemini_wrap.sh "Your task here"
   ```

## Template Structure

- `config/` - Configuration files (defaults and local overrides)
- `scripts/` - Core orchestration scripts
- `tools/rag/` - RAG (Retrieval-Augmented Generation) system
- `docs/` - Core documentation and operational guidelines
- `adapters/` - LLM integration templates
- `examples/` - Usage examples and patterns

## Core Features

- **RAG-powered context retrieval** - Local semantic search over codebases
- **Multi-provider LLM routing** - Seamless switching between providers
- **Contract-based context management** - Structured context requirements
- **Profile-driven configuration** - Adaptable settings for different models
- **Agent charter system** - Clear roles and operational guidelines

## Configuration

The template uses a layered configuration approach:

1. `config/default.toml` - System defaults (git-tracked)
2. `config/local.toml` - User overrides (git-ignored)
3. Environment variables - Runtime overrides

Copy `config/local.example.toml` to `config/local.toml` to customize.

## RAG System

The template includes a complete RAG system for local codebase understanding:

```bash
# Index your codebase
./scripts/rag/rag_refresh.sh

# Search context
./tools/rag/cli.py search "your query"
```

## Support

See the documentation in the `docs/` directory for detailed usage information.
