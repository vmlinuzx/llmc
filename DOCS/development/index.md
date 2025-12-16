# Development

Guides for contributing to LLMC.

---

## Getting Started

1. Read the [Contributing Guide](contributing.md)
2. Set up your [development environment](contributing.md#setup)
3. Run the [test suite](testing.md)

---

## Guides

| Guide | Description |
|-------|-------------|
| [Contributing](contributing.md) | How to contribute |
| [Testing](testing.md) | Test infrastructure and running tests |
| [Thunderdome](thunderdome.md) | Dialectical autocoding protocol |
| [Agent Contracts](agent-contracts.md) | AGENTS.md and LLM interaction rules |
| [TUI Style Guide](tui-style.md) | TUI component styling |
| [Release Process](release-process.md) | Versioning and releases |

---

## Quick Commands

```bash
# Run tests
pytest tests/

# Type checking
mypy llmc/

# Linting
ruff check .

# Format
ruff format .
```

---

## Project Structure

```
llmc/
├── llmc/           # Main package (CLI, TUI, docgen)
├── llmc_mcp/       # MCP server package
├── llmc_agent/     # Agent/chat package
├── tools/rag/      # RAG engine
├── tools/rag_nav/  # RAG navigation tools
├── tools/rag_repo/ # Repository management
├── tests/          # Test suite
├── scripts/        # Utility scripts
└── thunderdome/    # Testing infrastructure
```
