---
description: Deprecated. Use llmc repo register instead.
---

# DEPRECATED: llmc-rag-repo

> **⚠️ DEPRECATION NOTICE**
>
> This command is deprecated. Please use [`llmc repo`](llmc-cli.md#repo-management) instead.
>
> - `llmc-rag-repo add` → `llmc repo register`
> - `llmc-rag-repo list` → `llmc repo list`
> - `llmc-rag-repo inspect` → `llmc debug inspect`

This documentation is preserved for legacy reference.

## Original Documentation

`llmc-rag-repo` is a tool for managing which repositories are registered with the RAG system and performing maintenance on their workspaces.

### Usage

```bash
llmc-rag-repo [OPTIONS] COMMAND [ARGS]...
```

### Commands

- **add**: Register a new repository. Creates `.llmc/` workspace if missing.
- **list**: List all registered repositories and their status.
- **rm**: Unregister a repository (does not delete `.llmc/` workspace).
- **clean**: Clean a repository's workspace (rebuild index).
- **inspect**: detailed inspection of a repository's configuration and status.
- **validate**: Validate `llmc.toml` configuration.
