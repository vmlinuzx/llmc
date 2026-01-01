# Docgen v2 User Guide

**Deterministic, RAG-aware documentation generation for your codebase.**

---

## Overview

Docgen v2 automatically generates per-file documentation for your repository using:
- **SHA256-based idempotence** - Skip unchanged files
- **RAG integration** - Only generate docs for indexed, fresh files
- **Graph context** - Include entity and relationship information
- **Flexible backends** - Shell scripts, LLMs, HTTP APIs, or MCP

Documentation is generated in `DOCS/REPODOCS/` with deterministic output.

---

## Quick Start

### 1. Enable Docgen

Edit `llmc.toml`:

```toml
[docs.docgen]
enabled = true  # Enable docgen
backend = "shell"
output_dir = "DOCS/REPODOCS"
require_rag_fresh = true

[docs.docgen.shell]
script = "scripts/docgen_stub.py"  # Or your custom script
timeout_seconds = 60
```

### 2. Index Your Repository

Docgen requires RAG indexing first:

```bash
llmc-cli debug index
```

### 3. Generate Documentation

For all files:
```bash
llmc-cli docs generate --all
```

For a specific file:
```bash
llmc-cli docs generate path/to/file.py
```

Force regeneration (ignore SHA cache):
```bash
llmc-cli docs generate --all --force
```

### 4. Check Status

```bash
llmc-cli docs status
```

Output:
```
📊 Docgen Status
==================================================
Enabled:           True
Output directory:  DOCS/REPODOCS
Require RAG fresh: True

Files in RAG:      342
Docs generated:    156
Coverage:          156/342 (45%)
```

---

## How It Works

### Documentation Pipeline

1. **SHA256 Gate** - Skip files where SHA256 matches existing doc
2. **RAG Freshness Check** - Only process files indexed in RAG
3. **Graph Context** - Extract entities, relations, and enrichments
4. **Backend Invocation** - Call your docgen backend (script/LLM/API)
5. **Atomic Write** - Save documentation with SHA256 header

### Document Format

Generated docs have this structure:

```markdown
SHA256: abc123def456...

# Documentation for `path/to/file.py`

## Overview
...

## Graph Context
entities:
  - id: Entity_123
    kind: function
    name: process_data
    span: 10-25
    summary: Processes input data and returns results
...
```

### Backends

#### Shell Backend (Default)

Invokes an external script with JSON stdin:

```json
{
  "repo_root": "/path/to/repo",
  "relative_path": "src/main.py",
  "file_sha256": "abc123...",
  "source_contents": "...",
  "existing_doc_contents": "...",
  "graph_context": "..."
}
```

Script must output:
- `NO-OP: <reason>` - Skip generation
- `SHA256: <hash>\n<markdown>` - Generated doc

Example stub script: `scripts/docgen_stub.py`

#### LLM Backend (Future)

Direct LLM integration for documentation generation.

#### HTTP Backend (Future)

Call external documentation service via HTTP.

#### MCP Backend (Future)

Use Model Context Protocol for documentation.

---

## Configuration Reference

### Core Settings

```toml
[docs.docgen]
enabled = true|false              # Enable/disable docgen
backend = "shell"                 # Backend type
output_dir = "DOCS/REPODOCS"      # Output directory (relative to repo root)
require_rag_fresh = true|false    # Require RAG freshness check
```

### Shell Backend

```toml
[docs.docgen.shell]
script = "path/to/script.py"      # Script path (relative to repo root)
args = []                         # Optional script arguments
timeout_seconds = 60              # Execution timeout
```

### Daemon Integration (Future)

```toml
[docs.docgen]
daemon_interval_seconds = 3600    # How often to run
daemon_batch_size = 10            # Files per batch
```

---

## CLI Reference

### `llmc-cli docs generate`

Generate documentation for files.

**Usage:**
```bash
llmc-cli docs generate [OPTIONS] [PATH]
```

**Options:**
- `--all` - Generate for all indexed files
- `--force` - Ignore SHA gate (regenerate all)

**Examples:**
```bash
# Generate for all files
llmc-cli docs generate --all

# Generate for specific file
llmc-cli docs generate src/main.py

# Force regeneration
llmc-cli docs generate --all --force
```

### `llmc-cli docs status`

Show documentation generation status.

**Usage:**
```bash
llmc-cli docs status
```

Shows:
- Enabled status
- Output directory
- Files in RAG
- Docs coverage

---

## Custom Backend Scripts

### Script Interface

Your script receives JSON on stdin and must output to stdout.

**Input JSON:**
```json
{
  "repo_root": "/absolute/path/to/repo",
  "relative_path": "src/module/file.py",
  "file_sha256": "abc123...",
  "source_contents": "# Full file contents here\n...",
  "existing_doc_contents": "SHA256: old_hash\n# Old doc...",
  "graph_context": "=== GRAPH_CONTEXT_BEGIN ===\n..."
}
```

**Output Format:**

Skip generation:
```
NO-OP: SHA unchanged (abc123...)
```

Generate doc:
```
SHA256: abc123def456...

# Your Generated Documentation

Content here...
```

**Requirements:**
- SHA256 header must match input `file_sha256`
- Use graph_context to enrich documentation
- Handle timeouts gracefully
- Exit with code 0 on success

### Example Script

See `scripts/docgen_stub.py` for a working example.

---

## Troubleshooting

### "Docgen is disabled"

Enable in `llmc.toml`:
```toml
[docs.docgen]
enabled = true
```

### "RAG database not found"

Index your repository first:
```bash
llmc-cli debug index
```

### "Script not found"

Check script path in config:
```toml
[docs.docgen.shell]
script = "scripts/your_script.py"  # Relative to repo root
```

### "Failed to acquire docgen lock"

Another docgen process is running. Wait for it to complete or:
```bash
rm .llmc/docgen.lock
```

### "SKIP_NOT_INDEXED"

File not in RAG database. Run:
```bash
llmc-cli debug index
```

### "SKIP_STALE_INDEX"

File changed since indexing. Re-index:
```bash
llmc-cli debug index
```

---

## Best Practices

### 1. Regular Indexing

Keep RAG index fresh:
```bash
# After major changes
llmc-cli debug index
llmc-cli docs generate --all
```

### 2. Incremental Generation

Use default behavior (no `--force`) to only regenerate changed files.

### 3. Custom Scripts

Create domain-specific docgen scripts for your needs:
```python
#!/usr/bin/env python3
import json, sys

data = json.loads(sys.stdin.read())

# Your custom logic here
doc = generate_custom_docs(
    data["source_contents"],
    data["graph_context"]
)

print(f"SHA256: {data['file_sha256']}")
print()
print(doc)
```

### 4. Graph Context

Leverage the graph context for richer documentation:
- Entity summaries from enrichment
- Function calls and dependencies
- Module relationships

### 5. Gitignore

Add to `.gitignore`:
```
DOCS/REPODOCS/
.llmc/docgen.lock
```

---

## Advanced Usage

### Batch Processing

Process files in custom batches:
```python
from pathlib import Path
from llmc.docgen.orchestrator import DocgenOrchestrator
from llmc.docgen.config import load_docgen_backend
from llmc.rag.database import Database
import toml

# Load config
repo_root = Path(".")
with open("llmc.toml") as f:
    config = toml.load(f)

# Setup
backend = load_docgen_backend(repo_root, config)
db = Database(repo_root / ".llmc/rag/index_v2.db")

orchestrator = DocgenOrchestrator(
    repo_root=repo_root,
    backend=backend,
    db=db
)

# Process custom file list
files = [Path("src/a.py"), Path("src/b.py")]
results = orchestrator.process_batch(files)

# Check results
for path, result in results.items():
    print(f"{path}: {result.status}")
```

### Custom Output Directory

Change output location:
```toml
[docs.docgen]
output_dir = "docs/api"  # Instead of DOCS/REPODOCS
```

### Disable RAG Requirement

Generate docs for all files (not recommended):
```toml
[docs.docgen]
require_rag_fresh = false
```

---

## Roadmap

### ✅ Implemented (MVP)
- SHA256-based idempotence
- RAG freshness gating
- Graph context extraction
- Shell backend
- CLI commands
- Concurrency control

### 🔮 Future Enhancements
- LLM backend (Gemini, Claude, GPT-4)
- HTTP backend
- MCP backend
- Daemon integration (auto-generate on index)
- Incremental updates
- Documentation diff/review
- Multi-language support

---

## Support

Questions or issues? Check:
- Implementation plan: `DOCS/planning/IMPL_Docgen_v2.md`
- SDD: `DOCS/planning/SDD_Docgen_Enrichment_Module.md`
- Example script: `scripts/docgen_stub.py`

---

**Last Updated:** 2025-12-03  
**Version:** v2.0 MVP
