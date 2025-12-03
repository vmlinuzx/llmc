# Docgen V2 - Deterministic RAG-Aware Documentation Generation

**Status:** Development (feature/docgen-v2 branch)  
**Version:** 2.0  
**Created:** 2025-12-03

---

## Overview

Docgen V2 is a deterministic, RAG-aware documentation generation system that creates repository documentation by:
1. Loading knowledge graph context from RAG
2. Executing documentation generation backends (shell, LLM, HTTP, MCP)
3. Gating on SHA256 and RAG freshness to avoid redundant work

## Architecture

```
DocgenOrchestrator
    ├── Gating (SHA256, RAG freshness)
    ├── Graph Context (RAG integration)
    ├── Backend (Shell/LLM/HTTP/MCP)
    └── Locks (Concurrency control)
```

## Core Components

### 1. Orchestrator (`orchestrator.py`)
Coordinates the documentation generation pipeline:
- SHA256 gating (skip if unchanged)
- RAG freshness checks (skip if RAG stale)
- Graph context loading (cached per batch)
- Backend invocation
- File writing (atomic)

### 2. Graph Context (`graph_context.py`)
Extracts entities and relations from RAG knowledge graph:
- Loads `rag_graph.json` once per batch (performance optimization)
- Filters entities by file
- Formats deterministically
- Returns structured context for backends

**Performance:** 51x faster with caching (92ms → 1.8ms per file)

### 3. Backends (`backends/`)
Pluggable documentation generators:
- **Shell** - Execute external scripts (implemented)
- **LLM** - Direct LLM calls (planned)
- **HTTP** - Remote API calls (planned)
- **MCP** - MCP server integration (planned)

### 4. Gating (`gating.py`)
Deterministic skip logic:
- **SHA256 gating**: Skip if source unchanged and doc exists
- **RAG freshness**: Skip if RAG index stale for this file
- Ensures idempotency

### 5. Locking (`locks.py`)
Prevents concurrent docgen runs:
- File-based locking (fcntl)
- Timeout support
- Clean lock acquisition/release

### 6. Configuration (`config.py`)
Loads docgen settings from `llmc.toml`:
```toml
[docs.docgen]
enabled = true
backend = "shell"
output_dir = "DOCS/REPODOCS"
require_rag_fresh = true

[docs.docgen.shell]
script = "scripts/docgen.sh"
args = []
timeout_seconds = 60
```

### 7. Types (`types.py`)
Core type definitions:
- `DocgenBackend` protocol
- `DocgenResult` dataclass
- Status: "generated", "noop", "skipped"

---

## Usage

### From Code
```python
from llmc.docgen.orchestrator import DocgenOrchestrator
from llmc.docgen.config import load_docgen_backend
from tools.rag.database import Database

# Load configuration
backend = load_docgen_backend(repo_root, toml_data)
db = Database(repo_root)

# Create orchestrator
orchestrator = DocgenOrchestrator(
    repo_root=repo_root,
    backend=backend,
    db=db,
)

# Process single file
result = orchestrator.process_file(Path("llmc/docgen/README.md"))

# Process batch (optimized)
results = orchestrator.process_batch([
    Path("llmc/module1.py"),
    Path("llmc/module2.py"),
])
```

### From CLI
```bash
# Generate docs for all files
llmc docgen generate --all

# Generate for specific files
llmc docgen generate llmc/feature.py

# Force regeneration (skip SHA gate)
llmc docgen generate --force llmc/feature.py
```

---

## Performance

**Before optimization:**
- 92ms per file (loading full graph each time)
- 1,000 files = ~92 seconds

**After optimization:**
- Graph loaded once per batch
- 1.8ms per file (cached)
- 1,000 files = ~1.8 seconds
- **51x faster!**

---

## Design Decisions

See [`design_decisions.md`](./design_decisions.md) for detailed rationale on:
- DD-001: Explicit exit code handling (check=False)
- DD-002: Graph context caching
- DD-003: Type safety in configuration

---

## Testing

### Unit Tests
```bash
pytest tests/docgen/ -v
```

### Performance Tests
```bash
pytest tests/test_docgen_perf_ren.py -v
```

### Integration Tests
```bash
pytest tests/test_maasl_docgen.py -v
```

### Security Tests
```bash
pytest tests/security/test_docgen_*.py -v
```

---

## Known Limitations

### Security (See `tests/security/REPORTS/docgen_v2_security_audit.md`)
- ⚠️ Path traversal possible (no validation yet)
- ⚠️ No file size limits (resource exhaustion risk)
- ⚠️ Script execution from config (needs allowlist)

### Compatibility
- Linux only (locking uses fcntl)
- Requires RAG database

### Features
- Only shell backend implemented
- No incremental updates (full regen)
- No parallelization (sequential batch)

---

## Roadmap

### Phase 1: Core (Completed ✅)
- [x] Types and protocols
- [x] Gating logic
- [x] Shell backend
- [x] Orchestrator
- [x] Locking

### Phase 2: Performance (Completed ✅)
- [x] Graph caching
- [x] Batch optimization
- [x] Performance tests

### Phase 3: Security (In Progress)
- [ ] Path validation
- [ ] File size limits
- [ ] Script allowlist
- [ ] Audit logging
- [ ] Resource limits

### Phase 4: Features (Planned)
- [ ] LLM backend
- [ ] HTTP backend
- [ ] MCP backend
- [ ] Parallel processing
- [ ] Incremental updates
- [ ] CLI integration

---

## Contributing

When modifying docgen:

1. **Performance**: Consider batch operations (graph loading is expensive)
2. **Security**: Validate all external inputs (paths, config, file contents)
3. **Testing**: Add tests in `tests/docgen/` for functionality, `tests/security/` for security
4. **Documentation**: Update this README and design_decisions.md

---

## Troubleshooting

### "Graph index not found"
- Ensure RAG has indexed the repository
- Run `llmc rag build` to create index

### "RAG freshness check failed"
- RAG index is stale for this file
- Re-run enrichment or use `--skip-rag-check`

### "Script timed out"
- Increase timeout in config
- Check script for infinite loops

### "Lock acquisition failed"
- Another docgen process is running
- Wait or kill stale process
- Check `.llmc/docgen.lock`

---

## Files

```
llmc/docgen/
├── README.md              # This file
├── design_decisions.md    # Design rationale
├── __init__.py
├── types.py              # Core types
├── config.py             # Configuration loading
├── gating.py             # SHA256 and RAG gating
├── graph_context.py      # RAG graph integration
├── locks.py              # Concurrency control
├── orchestrator.py       # Main coordinator
└── backends/
    ├── __init__.py
    └── shell.py          # Shell script backend
```

---

**For detailed design decisions, see [`design_decisions.md`](./design_decisions.md)**  
**For security audit, see [`tests/security/REPORTS/docgen_v2_security_audit.md`](../../tests/security/REPORTS/docgen_v2_security_audit.md)**
