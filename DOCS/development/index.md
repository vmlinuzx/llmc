# Development

Guides for contributing to LLMC.

---

## Getting Started

---

## Guides

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
│   └── rag/        # RAG engine
├── llmc_mcp/       # MCP server package
├── llmc_agent/     # Agent/chat package
├── tests/          # Test suite
├── scripts/        # Utility scripts
└── thunderdome/    # Testing infrastructure
```
