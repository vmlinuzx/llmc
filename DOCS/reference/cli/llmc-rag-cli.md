---
description: Deprecated. Use llmc-cli instead.
---

# DEPRECATED: llmc-rag-cli

> **⚠️ DEPRECATION NOTICE**
>
> This command is deprecated. Please use [`llmc-cli`](llmc-cli.md) instead.
>
> - `llmc-rag-cli search` → `llmc analytics search`
> - `llmc-rag-cli` → `llmc-cli` (or `llmc`)

This documentation is preserved for legacy reference.

## Original Documentation

`llmc-rag-cli` was the original interface for interacting with the RAG index.

### Usage

```bash
llmc-rag-cli [OPTIONS] COMMAND [ARGS]...
```

### Commands

- **search**: Search the index.
- **ask**: Ask a question (replaced by `llmc chat`).
