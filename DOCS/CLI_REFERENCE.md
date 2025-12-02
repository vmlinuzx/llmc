# LLMC Unified CLI Reference

**Version:** 0.5.5  
**Last Updated:** 2025-12-02

---

## Installation

```bash
cd /path/to/llmc
pip install -e .
```

This installs the `llmc` command globally.

---

## Quick Start

```bash
# Initialize a new repository
llmc init

# Index the codebase
llmc index

# Search semantically
llmc search "how does authentication work?"

# View stats
llmc stats

# Launch TUI
llmc tui
```

---

## Command Reference

### Core Commands

#### `llmc init`
Bootstrap `.llmc/` workspace and configuration.

```bash
llmc init
```

Creates:
- `.llmc/` directory
- `llmc.toml` configuration file
- Empty database schema
- Log directory

---

#### `llmc --version`
Show version information and repository status.

```bash
llmc --version
# Output:
# LLMC v0.5.5
# Root: /home/user/src/myproject
# Config: Found
```

---

### RAG Commands

#### `llmc index`
Index the repository (full or incremental).

```bash
# Full index
llmc index

# Incremental (since commit)
llmc index --since HEAD~10

# Skip JSONL export
llmc index --no-export
```

**Options:**
- `--since SHA` - Only parse files changed since commit
- `--no-export` - Skip JSONL span export

---

#### `llmc search`
Semantic search over indexed code.

```bash
# Basic search
llmc search "JWT verification"

# Limit results
llmc search "database connection" --limit 20

# JSON output
llmc search "error handling" --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Output as JSON

---

#### `llmc inspect`
Deep dive into a file or symbol with graph context.

```bash
# Inspect by symbol
llmc inspect --symbol tools.rag.search.search_spans

# Inspect by file path
llmc inspect --path tools/rag/search.py

# Include full source
llmc inspect --path tools/rag/search.py --full

# Focus on specific line
llmc inspect --path tools/rag/search.py --line 42
```

**Options:**
- `--symbol, -s` - Symbol to inspect
- `--path, -p` - File path
- `--line, -l` - Line number
- `--full` - Include full source code

---

#### `llmc plan`
Generate a retrieval plan for a query.

```bash
# Generate plan
llmc plan "Where do we validate user input?"

# Adjust confidence threshold
llmc plan "authentication flow" --min-confidence 0.7

# More results
llmc plan "error handling" --limit 100
```

**Options:**
- `--limit N` - Max files/spans (default: 50)
- `--min-confidence FLOAT` - Minimum confidence (default: 0.6)

---

#### `llmc stats`
Print summary statistics for the current index.

```bash
# Human-readable stats
llmc stats

# JSON output
llmc stats --json
```

**Output:**
```
Repo: llmc
Files: 127
Spans: 1,543
Embeddings: 1,543
Enrichments: 1,234
Est. Remote Tokens: 308,600
```

---

#### `llmc doctor`
Diagnose RAG health and identify issues.

```bash
# Basic health check
llmc doctor

# Verbose output
llmc doctor --verbose
```

---

### Advanced RAG Commands

#### `llmc sync`
Incrementally update spans for selected files.

```bash
# Sync specific files
llmc sync --path tools/rag/search.py --path tools/rag/indexer.py

# Sync files changed since commit
llmc sync --since HEAD~5

# Read paths from stdin
git diff --name-only HEAD~10 | llmc sync --stdin
```

**Options:**
- `--path PATH` - Specific file paths (can be repeated)
- `--since SHA` - Sync files changed since commit
- `--stdin` - Read paths from stdin

---

#### `llmc enrich`
Run LLM-based enrichment on spans.

```bash
# Dry run (preview work)
llmc enrich --dry-run

# Enrich 50 spans
llmc enrich --limit 50

# Use specific model
llmc enrich --model gpt-4 --limit 10

# Skip recently changed files
llmc enrich --cooldown 300
```

**Options:**
- `--limit N` - Max spans to enrich (default: 10)
- `--dry-run` - Preview without running LLM
- `--model NAME` - Model identifier (default: local-qwen)
- `--cooldown N` - Skip spans changed within N seconds

---

#### `llmc embed`
Generate embeddings for spans.

```bash
# Dry run
llmc embed --dry-run

# Generate embeddings
llmc embed --limit 100

# Use specific model
llmc embed --model sentence-transformers/all-MiniLM-L6-v2

# Specify dimension
llmc embed --dim 384
```

**Options:**
- `--limit N` - Max spans (default: 10)
- `--dry-run` - Preview without generating
- `--model NAME` - Embedding model (default: auto)
- `--dim N` - Embedding dimension (default: 0 = auto)

---

#### `llmc graph`
Build a schema graph for the repository.

```bash
# Build graph (requires enrichment)
llmc graph

# Allow empty enrichment
llmc graph --no-require-enrichment

# Custom output path
llmc graph --output /tmp/my_graph.json
```

**Options:**
- `--require-enrichment / --no-require-enrichment` - Require enrichment data (default: true)
- `--output PATH` - Output path (default: .llmc/rag_graph.json)

---

#### `llmc export`
Export all RAG data to tar.gz archive.

```bash
# Export with auto-generated name
llmc export

# Custom output path
llmc export --output /tmp/rag_backup.tar.gz
```

**Options:**
- `--output, -o PATH` - Output archive path

---

#### `llmc benchmark`
Run embedding quality benchmark.

```bash
# Run benchmark
llmc benchmark

# JSON output
llmc benchmark --json

# Adjust thresholds
llmc benchmark --top1-threshold 0.8 --margin-threshold 0.15
```

**Options:**
- `--json` - Emit metrics as JSON
- `--top1-threshold FLOAT` - Minimum top-1 accuracy (default: 0.75)
- `--margin-threshold FLOAT` - Minimum margin (default: 0.1)

---

### Navigation Commands

#### `llmc nav search`
Semantic/structural search using graph.

```bash
# Search
llmc nav search "authentication middleware"

# Limit results
llmc nav search "database query" --limit 20

# JSON output
llmc nav search "error handler" --json
```

**Options:**
- `--limit, -n N` - Max results (default: 10)
- `--json` - Emit JSON output

---

#### `llmc nav where-used`
Find where a symbol is used.

```bash
# Find usages
llmc nav where-used search_spans

# Limit results
llmc nav where-used Database --limit 50

# JSON output
llmc nav where-used index_repo --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Emit JSON output

---

#### `llmc nav lineage`
Show symbol lineage (dependencies).

```bash
# Show lineage
llmc nav lineage search_spans

# Deeper traversal
llmc nav lineage Database --depth 5

# JSON output
llmc nav lineage index_repo --json
```

**Options:**
- `--depth N` - Max depth to traverse (default: 2)
- `--json` - Emit JSON output

---

### Service Management

#### `llmc service start`
Start the RAG service daemon.

```bash
# Start with default interval (180s)
llmc service start

# Custom interval
llmc service start --interval 300
```

**Options:**
- `--interval N` - Enrichment cycle interval in seconds (default: 180)

**Prerequisites:**
- At least one repository registered (`llmc service repo add`)
- Systemd available

---

#### `llmc service stop`
Stop the RAG service daemon.

```bash
llmc service stop
```

---

#### `llmc service restart`
Restart the RAG service daemon.

```bash
# Restart with current settings
llmc service restart

# Update interval on restart
llmc service restart --interval 120
```

**Options:**
- `--interval N` - Update enrichment interval

---

#### `llmc service status`
Show service status and registered repos.

```bash
llmc service status
```

**Output:**
```
✅ Service: RUNNING (PID 9280)

📂 Registered repos: 1
   • /home/user/src/llmc

⏱️  Interval: 180s
   Last cycle: 2025-12-02T20:36:24.161086+00:00

📊 Systemd Status:
   Active: active (running) since Tue 2025-12-02 11:50:10 EST
   Main PID: 9280 (python3)
```

---

#### `llmc service logs`
View service logs via journalctl.

```bash
# View last 50 lines
llmc service logs

# View last 100 lines
llmc service logs --lines 100

# Follow logs (like tail -f)
llmc service logs --follow
```

**Options:**
- `--follow, -f` - Follow log output
- `--lines, -n N` - Number of lines to show (default: 50)

---

#### `llmc service enable`
Enable service to start on user login.

```bash
llmc service enable
```

---

#### `llmc service disable`
Disable service from starting on user login.

```bash
llmc service disable
```

---

#### `llmc service repo add`
Register a repository for enrichment.

```bash
llmc service repo add /path/to/repo
```

---

#### `llmc service repo remove`
Unregister a repository.

```bash
llmc service repo remove /path/to/repo
```

---

#### `llmc service repo list`
List all registered repositories.

```bash
llmc service repo list
```

**Output:**
```
Registered repositories (2):

1. /home/user/src/llmc
2. /home/user/src/myproject
```

---

### TUI Commands

#### `llmc tui`
Launch the interactive TUI dashboard.

```bash
llmc tui
```

Features:
- Live system metrics
- Service status monitoring
- Code search interface
- RAG health diagnostics
- Configuration editor

---

#### `llmc monitor`
Alias for `llmc tui`.

```bash
llmc monitor
```

---

## Configuration

The `llmc.toml` file in your repository root controls LLMC behavior.

### Example Configuration

```toml
[rag]
# Embedding model
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
embedding_dim = 384

# Enrichment settings
enrichment_backend = "ollama"
enrichment_model = "qwen2.5:7b"

[service]
# Service interval (seconds)
interval = 180

# Max failures per span before skipping
max_failures_per_span = 3

[logging]
# Log rotation
enable_rotation = true
max_file_size_mb = 10
keep_jsonl_lines = 1000
auto_rotation_interval = 3600
```

---

## Workflows

### Initial Setup

```bash
cd /path/to/your/project
llmc init
llmc index
llmc service repo add .
llmc service start
llmc tui
```

### Daily Development

```bash
# After making changes
llmc sync --since HEAD~1

# Search for something
llmc search "authentication"

# Check service health
llmc service status
```

### Troubleshooting

```bash
# Check RAG health
llmc doctor --verbose

# View service logs
llmc service logs --follow

# Rebuild index
llmc index

# Rebuild graph
llmc graph
```

---

## Migration from Legacy Commands

| Legacy Command | New Unified Command |
|:---------------|:--------------------|
| `python -m tools.rag.cli index` | `llmc index` |
| `python -m tools.rag.cli search` | `llmc search` |
| `python -m tools.rag.cli inspect` | `llmc inspect` |
| `python -m tools.rag.cli plan` | `llmc plan` |
| `python -m tools.rag.cli stats` | `llmc stats` |
| `python -m tools.rag.cli doctor` | `llmc doctor` |
| `scripts/llmc-tui` | `llmc tui` |

**Note:** Legacy commands still work but are deprecated. The unified CLI provides better discoverability and consistent UX.

---

## Shell Completion

Install shell completion for better UX:

```bash
# Bash
llmc --install-completion bash

# Zsh
llmc --install-completion zsh

# Fish
llmc --install-completion fish
```

---

## Troubleshooting

### "No index database found"

Run `llmc index` first to create the index.

### "Systemd not available"

The service management commands require systemd. Use `llmc-rag` script for fallback fork() mode.

### "Module not found" errors

Ensure you've installed LLMC:
```bash
pip install -e .
```

### Performance Issues

Check service status and logs:
```bash
llmc service status
llmc service logs --lines 100
```

---

## See Also

- [SDD: Unified CLI v2](../planning/SDD_Unified_CLI_v2.md) - Design document
- [AGENTS.md](../../AGENTS.md) - Agent protocols and workflows
- [ROADMAP.md](../ROADMAP.md) - Project roadmap
