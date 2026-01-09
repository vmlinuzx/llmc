---
description: Deprecated. Use llmc service instead.
---

# DEPRECATED: llmc-rag-daemon

> **⚠️ DEPRECATION NOTICE**
>
> This command is deprecated. Please use [`llmc service`](llmc-cli.md#service-management) instead.
>
> - `llmc-rag-daemon` → `llmc service start --daemon`
> - `llmc-rag-service` → `llmc service`

This documentation is preserved for legacy reference.

## Original Documentation

`llmc-rag-daemon` is the background process that keeps repositories indexed and enriched.

### Usage

```bash
llmc-rag-daemon [OPTIONS]
```

### Options

- `--interval INTEGER`: Sync interval in seconds (default: 300).
- `--single-run`: Run once and exit (good for debugging).
- `--verbose / --no-verbose`: Enable verbose logging.
