# RAG Tools Usage Guide

## Installation

The RAG tools require proper package installation to work from any directory.

### Option 1: Editable Install (Development - Recommended)

From the repository root:

```bash
# Using the project's venv (recommended)
.venv/bin/pip install -e .

# Or create your own venv
python3 -m venv myenv
source myenv/bin/activate
pip install -e .
```

**Why editable mode?** This links the package to your repository, so changes to code are immediately available without reinstalling.

### Option 2: Regular Install

```bash
pip install .
```

### Verifying Installation

Test that both `llmc` and `tools` modules are available:

```bash
python3 -c "import llmc; import llmc.rag; print('✅ Installation successful')"
```

## Running RAG CLI Commands

### From Repository Context

When the package is installed in editable mode with the venv:

```bash
# Use the venv python
.venv/bin/python3 -m llmc.rag.cli --help

# Or activate the venv first
source .venv/bin/activate
python3 -m llmc.rag.cli --help
```

### From Any Directory

Once installed, RAG tools work from any directory:

```bash
# Navigate to any git repository
cd ~/my-project

# Index the repository
python3 -m llmc.rag.cli index

# Search indexed content
python3 -m llmc.rag.cli search "authentication logic"

# View statistics
python3 -m llmc.rag.cli stats
```

## Common Commands

### Indexing

```bash
# Full index of current repository
python3 -m llmc.rag.cli index

# Index only files changed since a commit
python3 -m llmc.rag.cli index --since HEAD~5

# Skip JSON export (faster)
python3 -m llmc.rag.cli index --no-export
```

### Searching

```bash
# Vector search
python3 -m llmc.rag.cli search "JWT validation" --limit 10

# JSON output
python3 -m llmc.rag.cli search "error handling" --json

# With debug info
python3 -m llmc.rag.cli search "database connection" --debug
```

### Statistics

```bash
# Human-readable stats
python3 -m llmc.rag.cli stats

# JSON format
python3 -m llmc.rag.cli stats --json
```

### Schema Graph

```bash
# Build schema graph
python3 -m llmc.rag.cli graph

# Allow empty enrichment
python3 -m llmc.rag.cli graph --allow-empty-enrichment
```

## Troubleshooting

### ModuleNotFoundError: No module named 'llmc'

**Problem:** The package is not properly installed or you're using system Python instead of the venv.

**Solutions:**

1. **Check if using venv:**
   ```bash
   which python3
   # Should show: /path/to/llmc/.venv/bin/python3
   ```

2. **Activate venv:**
   ```bash
   source .venv/bin/activate
   ```

3. **Reinstall package:**
   ```bash
   .venv/bin/pip install -e . --no-deps
   ```

4. **Verify installation:**
   ```bash
   python3 -c "import llmc; import llmc.rag; print('OK')"
   ```

### Import Errors from tools/rag/indexer.py

**Problem:** Old installation without `llmc` package mapping.

**Solution:**

1. Check installed version:
   ```bash
   pip show llmcwrapper
   ```

2. Should be version 0.5.5 or later. If older, reinstall:
   ```bash
   .venv/bin/pip install -e . --force-reinstall --no-deps
   ```

### Python Path Issues

The RAG modules are now part of the main `llmc` package. With an editable install, no special path handling is needed.

**Manual override** (not recommended):
```bash
export PYTHONPATH=/path/to/llmc:$PYTHONPATH
python3 -m llmc.rag.cli index
```

## Architecture Notes

- **Module Structure:** RAG tools are in `llmc/rag/`, integrated with the main LLMC package
- **Import:** RAG modules are directly importable from `llmc.rag`
- **Editable Install:** Creates mapping of `llmc` and `llmcwrapper` packages
- **CLI Entry Point:** Tools are accessed via `python3 -m llmc.rag.cli`

## Related Documents

- [Main README](../../README.md)
- [RAG Architecture](../../DOCS/README_RAG.md)
- [MCP Server Documentation](../../DOCS/MCP/)

---

**Last Updated:** 2025-12-02  
**Bug Fix:** Roswaal P1 - Module Import Error Outside Repository
