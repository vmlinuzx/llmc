# Migration Guide: Legacy Commands → Unified CLI

**Date:** 2025-12-02  
**Version:** 0.5.5+

---

## Overview

LLMC now provides a unified `llmc` command that consolidates all functionality under a single entry point. Legacy commands still work but are considered deprecated.

---

## Quick Reference

| Legacy Command | Unified CLI Command | Status |
|:---------------|:--------------------|:-------|
| `python -m tools.rag.cli index` | `llmc index` | ✅ Recommended |
| `python -m tools.rag.cli search` | `llmc search` | ✅ Recommended |
| `python -m tools.rag.cli inspect` | `llmc inspect` | ✅ Recommended |
| `python -m tools.rag.cli plan` | `llmc plan` | ✅ Recommended |
| `python -m tools.rag.cli stats` | `llmc stats` | ✅ Recommended |
| `python -m tools.rag.cli doctor` | `llmc doctor` | ✅ Recommended |
| `python -m tools.rag.cli sync` | `llmc sync` | ✅ Recommended |
| `python -m tools.rag.cli enrich` | `llmc enrich` | ✅ Recommended |
| `python -m tools.rag.cli embed` | `llmc embed` | ✅ Recommended |
| `python -m tools.rag.cli graph` | `llmc graph` | ✅ Recommended |
| `python -m tools.rag.cli export` | `llmc export` | ✅ Recommended |
| `python -m tools.rag.cli benchmark` | `llmc benchmark` | ✅ Recommended |
| `python -m tools.rag.cli nav search` | `llmc nav search` | ✅ Recommended |
| `python -m tools.rag.cli nav where-used` | `llmc nav where-used` | ✅ Recommended |
| `python -m tools.rag.cli nav lineage` | `llmc nav lineage` | ✅ Recommended |
| `scripts/llmc-tui` | `llmc tui` | ❌ Removed |
| `scripts/llmc-rag` (service) | `llmc service` | ❌ Removed |

---

## Installation

The unified CLI is installed automatically when you install LLMC:

```bash
pip install -e .
```

This creates the `llmc` command in your PATH.

---

## Breaking Changes

### None (Backwards Compatible)

All legacy commands continue to work. The unified CLI is additive, not replacing.

---

## New Features in Unified CLI

### 1. **Service Management**

The biggest change is service management, which now uses subcommands:

**Legacy:**
```bash
llmc-rag start --interval 180
llmc-rag stop
llmc-rag status
```

**Unified:**
```bash
llmc service start --interval 180
llmc service stop
llmc service status
llmc service logs -f
```

**New capabilities:**
- `llmc service enable` - Auto-start on login
- `llmc service disable` - Disable auto-start
- `llmc service restart` - Restart with optional interval update
- `llmc service repo add/remove/list` - Manage registered repos

### 2. **Consistent Help System**

Every command has built-in help:

```bash
llmc --help
llmc search --help
llmc service --help
llmc nav --help
```

### 3. **Shell Completion**

Install completion for your shell:

```bash
llmc --install-completion bash
llmc --install-completion zsh
llmc --install-completion fish
```

### 4. **Unified Version Info**

```bash
llmc --version
# Output:
# LLMC v0.5.5
# Root: /home/user/src/myproject
# Config: Found
```

---

## Migration Steps

### For Individual Users

**No action required.** Both old and new commands work.

**Recommended:**
1. Start using `llmc` commands in new scripts
2. Update your shell aliases
3. Install shell completion for better UX

### For Scripts and Automation

**Option 1: No Change (Safest)**
Keep using legacy commands. They still work.

**Option 2: Gradual Migration**
Update scripts one at a time:

```bash
# Before
python -m tools.rag.cli index

# After
llmc index
```

**Option 3: Alias Wrapper**
Add aliases to your `.bashrc` or `.zshrc`:

```bash
alias rag='llmc'
alias rag-search='llmc search'
alias rag-index='llmc index'
```

### For CI/CD Pipelines

**Recommendation:** Pin to specific commands and test before deploying.

```yaml
# GitHub Actions example
- name: Index codebase
  run: llmc index

- name: Run RAG health check
  run: llmc doctor
```

---

## Command Mapping Details

### RAG Commands

```bash
# Index
python -m tools.rag.cli index --since HEAD~10
llmc index --since HEAD~10

# Search
python -m tools.rag.cli search "query" --limit 20 --json
llmc search "query" --limit 20 --json

# Inspect
python -m tools.rag.cli inspect --path tools/rag/search.py --full
llmc inspect --path tools/rag/search.py --full

# Plan
python -m tools.rag.cli plan "query" --limit 50
llmc plan "query" --limit 50

# Stats
python -m tools.rag.cli stats --json
llmc stats --json

# Doctor
python -m tools.rag.cli doctor --verbose
llmc doctor --verbose
```

### Advanced RAG Commands

```bash
# Sync
python -m tools.rag.cli sync --since HEAD~5
llmc sync --since HEAD~5

# Enrich
python -m tools.rag.cli enrich --limit 50 --dry-run
llmc enrich --limit 50 --dry-run

# Embed
python -m tools.rag.cli embed --limit 100
llmc embed --limit 100

# Graph
python -m tools.rag.cli graph --output /tmp/graph.json
llmc graph --output /tmp/graph.json

# Export
python -m tools.rag.cli export --output backup.tar.gz
llmc export --output backup.tar.gz

# Benchmark
python -m tools.rag.cli benchmark --json
llmc benchmark --json
```

### Navigation Commands

```bash
# Nav search
python -m tools.rag.cli nav search "query" --limit 10
llmc nav search "query" --limit 10

# Where-used
python -m tools.rag.cli nav where-used symbol_name
llmc nav where-used symbol_name

# Lineage
python -m tools.rag.cli nav lineage symbol_name --depth 3
llmc nav lineage symbol_name --depth 3
```

### Service Management

**Legacy (llmc-rag script):**
```bash
llmc-rag start --interval 180
llmc-rag stop
llmc-rag status
llmc-rag logs -f
```

**Unified:**
```bash
llmc service start --interval 180
llmc service stop
llmc service status
llmc service logs -f
```

**New commands (no legacy equivalent):**
```bash
llmc service enable
llmc service disable
llmc service restart --interval 120
llmc service repo add /path/to/repo
llmc service repo remove /path/to/repo
llmc service repo list
```

### TUI

```bash
# Legacy
scripts/llmc-tui

# Unified
llmc tui

# Alias
llmc monitor
```

---

## Deprecation Timeline

**Current (v0.5.5):**
- ✅ Unified CLI available
- ✅ Legacy module commands (`python -m ...`) still work
- ❌ Legacy wrapper scripts (`scripts/llmc-*`) removed
- ℹ️ No deprecation warnings on modules

**Future (v0.6.0 - Estimated Q1 2026):**
- ⚠️ Deprecation warnings added to legacy commands
- ✅ Both old and new commands work
- 📖 Documentation updated to show unified CLI only

**Future (v0.7.0 - Estimated Q2 2026):**
- ❌ Legacy `python -m tools.rag.cli` commands removed
- ✅ `llmc-rag` and `llmc-tui` scripts still work (wrapper mode)
- ✅ Unified CLI is the only documented interface

---

## Benefits of Unified CLI

### 1. **Discoverability**

```bash
llmc --help
# Shows all available commands at a glance
```

### 2. **Consistency**

All commands follow the same patterns:
- `--help` for help
- `--json` for JSON output
- `--verbose` for detailed output

### 3. **Grouping**

Related commands are grouped:
- `llmc service *` - Service management
- `llmc nav *` - Navigation
- `llmc *` - Core RAG operations

### 4. **Better Error Messages**

```bash
$ llmc search
# Error: Missing argument 'QUERY'
# Usage: llmc search [OPTIONS] QUERY
```

### 5. **Shell Completion**

Tab completion works for all commands and options.

---

## Troubleshooting

### "Command not found: llmc"

**Solution:** Reinstall LLMC:
```bash
pip install -e .
```

### "Module not found" errors

**Solution:** Ensure you're in the correct environment:
```bash
which python3
pip list | grep llmc
```

### Legacy commands still preferred

**Solution:** That's fine! They still work and will continue to work.

---

## Getting Help

- **CLI Reference:** [DOCS/CLI_REFERENCE.md](CLI_REFERENCE.md)
- **Design Document:** [DOCS/planning/SDD_Unified_CLI_v2.md](planning/SDD_Unified_CLI_v2.md)
- **Roadmap:** [DOCS/ROADMAP.md](../ROADMAP.md)

---

## Feedback

If you encounter issues with the unified CLI or have suggestions, please:

1. Check the [CLI Reference](CLI_REFERENCE.md)
2. Run `llmc doctor` to diagnose issues
3. File an issue with reproduction steps

---

**Last Updated:** 2025-12-02  
**Applies to:** LLMC v0.5.5+
