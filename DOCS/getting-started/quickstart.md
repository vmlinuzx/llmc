# Quickstart Guide

This guide will walk you through setting up LLMC to index a single repository and perform your first semantic search.

**Prerequisite**: You must have [installed LLMC](installation.md).

---

## 1. Register a Repository

Tell LLMC which repository you want to index. You can use the `llmc` repo itself as a test case.

```bash
# Register the current directory (assuming you are in llmc root)
llmc-rag-repo add $(pwd)
```

This creates a hidden `.llmc/` directory in the target repo to store local configuration and the RAG index.

## 2. Start the Service

The RAG service handles indexing, embedding, and enrichment in the background.

```bash
# Register the repo with the service (tells the daemon to watch it)
llmc-rag-service register $(pwd)

# Start the service in the background
llmc-rag-service start --daemon
```

You can check if it's running:
```bash
llmc-rag-service status
```

## 3. Monitor Indexing

The indexing process takes a few minutes depending on the repo size. It involves:
1.  **Scanning** files.
2.  **Slicing** code into functions and classes.
3.  **Embedding** text for vector search.
4.  **Enriching** code with LLM-generated summaries.

You can watch the progress using the TUI:

```bash
llmc-tui
```

Look for the "Pending" counts dropping to zero.

## 4. Run Your First Search

Once the index is populated, you can ask questions about the codebase.

**Using the CLI:**

```bash
# Search for concepts
python -m tools.rag.cli search --repo $(pwd) "how does the scheduler work"
```

**Using the TUI:**

1.  Launch `llmc-tui`.
2.  Navigate to the **Search** tab (press `2`).
3.  Type your query and press Enter.

## 5. View "Where Used" (Graph)

LLMC also builds a dependency graph. You can check where specific symbols are used.

```bash
# Find usages of a class or function
python -m tools.rag.cli where-used --repo $(pwd) "RAGService"
```

## Next Steps

- **[Core Concepts](concepts.md)**: Learn about what's happening under the hood.
- **[Configuration](../user-guide/configuration.md)**: Customize embedding models and enrichment providers.
- **[MCP Integration](../operations/mcp-integration.md)**: Connect LLMC to Claude Desktop.
