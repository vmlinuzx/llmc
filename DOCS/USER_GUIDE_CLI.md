# LLMC CLI User Guide

This guide covers the path-safety related CLI helpers exposed by `tools.rag_repo.cli_entry`.

## Quickstart

```bash
python -m tools.rag_repo.cli_entry doctor-paths --repo /path/to/repo --json
python -m tools.rag_repo.cli_entry snapshot --repo /path/to/repo --name snap.tar.gz --force --json
python -m tools.rag_repo.cli_entry clean --repo /path/to/repo --force --json
```

- `--json` prints machine-friendly output.
- `--force` is required for destructive ops (`clean`).

## Exit Codes

- `0` — success
- `2` — user/path/policy error (bad workspace, traversal attempt, missing `--force`, etc.)
- `1` — unexpected failure (trace in logs; CLI prints a concise message)

## Examples

**Doctor check**

```bash
python -m tools.rag_repo.cli_entry doctor-paths --repo ~/src/llmc --json
```

**Snapshot workspace**

```bash
python -m tools.rag_repo.cli_entry snapshot --repo ~/src/llmc --name snapshot-$(date +%s).tar.gz --force --json
```

**Clean workspace contents**

```bash
python -m tools.rag_repo.cli_entry clean --repo ~/src/llmc --force --json
```

