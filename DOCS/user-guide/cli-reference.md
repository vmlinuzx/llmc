# LLMC Unified CLI Reference

**Version:** 0.6.0  
**Last Updated:** 2025-12-04

---

## Installation

```bash
cd /path/to/llmc
pip install -e .
```

This installs the `llmc` command globally.

---

## Command Structure Overview

The CLI is organized into logical groups for discoverability:

```
llmc
├── init              # Bootstrap workspace
├── config            # Interactive config TUI
├── tui               # Main TUI dashboard
├── monitor           # Quick log monitoring
│
├── service           # Daemon management
│   ├── start/stop/restart/status/logs
│   ├── enable/disable
│   └── repo (add/remove/list)
│
├── analytics         # Search, stats & insights
│   ├── search        # Semantic search
│   ├── stats         # Index statistics
│   ├── benchmark     # Embedding quality
│   ├── where-used    # Symbol usages
│   └── lineage       # Symbol dependencies
│
├── debug             # Troubleshooting & diagnostics
│   ├── index         # Reindex repo
│   ├── doctor        # RAG health check
│   ├── sync          # Incremental update
│   ├── enrich        # Enrichment tasks
│   ├── embed         # Embedding jobs
│   ├── graph         # Build schema graph
│   ├── plan          # Retrieval plan
│   ├── inspect       # Deep dive
│   ├── export        # Export RAG data
│   └── enrich-status # Enrichment metrics
│
├── docs              # LLMC documentation
│   ├── readme
│   ├── quickstart
│   ├── userguide
│   ├── generate      # Generate docs
│   └── status        # Docgen status
│
└── usertest          # RUTA testing
    ├── init
    └── run
```

---

## Quick Start

```bash
# Initialize a new repository
llmc init

# Start the RAG service
llmc service repo add .
llmc service start

# Search semantically
llmc analytics search "how does authentication work?"

# View stats
llmc analytics stats

# Launch TUI
llmc tui
```

---

## Core Commands

### `llmc init`
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

### `llmc config`
Launch the interactive enrichment configuration TUI.

```bash
llmc config
```

---

### `llmc tui`
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

### `llmc monitor`
Monitor service logs (alias for `llmc service logs -f`).

```bash
llmc monitor
```

---

### `llmc --version`
Show version information and repository status.

```bash
llmc --version
# Output:
# LLMC v0.6.0
# Root: /home/user/src/myproject
# Config: Found
```

---

## Analytics Commands

### `llmc analytics search`
Semantic search over indexed code.

```bash
# Basic search
llmc analytics search "JWT verification"

# Limit results
llmc analytics search "database connection" --limit 20

# JSON output
llmc analytics search "error handling" --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Output as JSON

---

### `llmc analytics stats`
Print summary statistics for the current index.

```bash
# Human-readable stats
llmc analytics stats

# JSON output
llmc analytics stats --json
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

### `llmc analytics benchmark`
Run embedding quality benchmark.

```bash
# Run benchmark
llmc analytics benchmark

# JSON output
llmc analytics benchmark --json

# Adjust thresholds
llmc analytics benchmark --top1-threshold 0.8 --margin-threshold 0.15
```

**Options:**
- `--json` - Emit metrics as JSON
- `--top1-threshold FLOAT` - Minimum top-1 accuracy (default: 0.75)
- `--margin-threshold FLOAT` - Minimum margin (default: 0.1)

---

### `llmc analytics where-used`
Find where a symbol is used.

```bash
# Find usages
llmc analytics where-used search_spans

# Limit results
llmc analytics where-used Database --limit 50

# JSON output
llmc analytics where-used index_repo --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Emit JSON output

---

### `llmc analytics lineage`
Show symbol lineage (dependencies).

```bash
# Show lineage
llmc analytics lineage search_spans

# Deeper traversal
llmc analytics lineage Database --depth 5

# JSON output
llmc analytics lineage index_repo --json
```

**Options:**
- `--depth N` - Max depth to traverse (default: 2)
- `--json` - Emit JSON output

---

## Debug Commands

### `llmc debug index`
Index the repository (full or incremental).

```bash
# Full index
llmc debug index

# Incremental (since commit)
llmc debug index --since HEAD~10

# Skip JSONL export
llmc debug index --no-export
```

**Options:**
- `--since SHA` - Only parse files changed since commit
- `--no-export` - Skip JSONL span export

---

### `llmc debug doctor`
Diagnose RAG health and identify issues.

```bash
# Basic health check
llmc debug doctor

# Verbose output
llmc debug doctor --verbose
```

---

### `llmc debug sync`
Incrementally update spans for selected files.

```bash
# Sync specific files
llmc debug sync --path llmc/rag/search.py --path llmc/rag/indexer.py

# Sync files changed since commit
llmc debug sync --since HEAD~5

# Read paths from stdin
git diff --name-only HEAD~10 | llmc debug sync --stdin
```

**Options:**
- `--path PATH` - Specific file paths (can be repeated)
- `--since SHA` - Sync files changed since commit
- `--stdin` - Read paths from stdin

---

### `llmc debug enrich`
Run LLM-based enrichment on spans.

```bash
# Dry run (preview work)
llmc debug enrich --dry-run

# Enrich 50 spans
llmc debug enrich --limit 50

# Use specific model
llmc debug enrich --model gpt-4 --limit 10

# Skip recently changed files
llmc debug enrich --cooldown 300
```

**Options:**
- `--limit N` - Max spans to enrich (default: 10)
- `--dry-run` - Preview without running LLM
- `--model NAME` - Model identifier (default: local-qwen)
- `--cooldown N` - Skip spans changed within N seconds
- `--code-first` - Use code-first prioritization
- `--no-code-first` - Disable code-first prioritization
- `--starvation-ratio` - High:Low ratio for mixing priorities (e.g., 5:1)
- `--show-weights` - In dry-run, show path weights and priority
- `--json` - Emit machine-readable JSON

---

### `llmc debug embed`
Generate embeddings for spans.

```bash
# Dry run
llmc debug embed --dry-run

# Generate embeddings
llmc debug embed --limit 100

# Use specific model
llmc debug embed --model sentence-transformers/all-MiniLM-L6-v2

# Specify dimension
llmc debug embed --dim 384
```

**Options:**
- `--limit N` - Max spans (default: 10)
- `--dry-run` - Preview without generating
- `--model NAME` - Embedding model (default: auto)
- `--dim N` - Embedding dimension (default: 0 = auto)

---

### `llmc debug graph`
Build a schema graph for the repository.

```bash
# Build graph (requires enrichment)
llmc debug graph

# Allow empty enrichment
llmc debug graph --no-require-enrichment

# Custom output path
llmc debug graph --output /tmp/my_graph.json
```

**Options:**
- `--require-enrichment / --no-require-enrichment` - Require enrichment data (default: true)
- `--output PATH` - Output path (default: .llmc/rag_graph.json)

---

### `llmc debug plan`
Generate a retrieval plan for a query.

```bash
# Generate plan
llmc debug plan "Where do we validate user input?"

# Adjust confidence threshold
llmc debug plan "authentication flow" --min-confidence 0.7

# More results
llmc debug plan "error handling" --limit 100
```

**Options:**
- `--limit N` - Max files/spans (default: 50)
- `--min-confidence FLOAT` - Minimum confidence (default: 0.6)

---

### `llmc debug inspect`
Deep dive into a file or symbol with graph context.

```bash
# Inspect by symbol
llmc debug inspect --symbol llmc.rag.search.search_spans

# Inspect by file path
llmc debug inspect --path llmc/rag/search.py

# Include full source
llmc debug inspect --path llmc/rag/search.py --full

# Focus on specific line
llmc debug inspect --path llmc/rag/search.py --line 42
```

**Options:**
- `--symbol, -s` - Symbol to inspect
- `--path, -p` - File path
- `--line, -l` - Line number
- `--full` - Include full source code

---

### `llmc debug export`
Export all RAG data to tar.gz archive.

```bash
# Export with auto-generated name
llmc debug export

# Custom output path
llmc debug export --output /tmp/rag_backup.tar.gz
```

**Options:**
- `--output, -o PATH` - Output archive path

---

### `llmc debug enrich-status`
Show enrichment runner metrics and code-first status.

```bash
# Human-readable output
llmc debug enrich-status

# JSON output
llmc debug enrich-status --json
```

---

### `llmc docs generate`
Generate documentation for repository files.

```bash
llmc docs generate
```

---

### `llmc docs status`
Show documentation generation status.

```bash
llmc docs status
```

---

## Service Management

### `llmc service start`
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

### `llmc service stop`
Stop the RAG service daemon.

```bash
llmc service stop
```

---

### `llmc service restart`
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

### `llmc service status`
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

### `llmc service logs`
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

### `llmc service enable`
Enable service to start on user login.

```bash
llmc service enable
```

---

### `llmc service disable`
Disable service from starting on user login.

```bash
llmc service disable
```

---

### `llmc service repo add`
Register a repository for enrichment.

```bash
llmc service repo add /path/to/repo
```

---

### `llmc service repo remove`
Unregister a repository.

```bash
llmc service repo remove /path/to/repo
```

---

### `llmc service repo list`
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

## Documentation Commands

### `llmc docs readme`
Display the LLMC README.

```bash
llmc docs readme
```

---

### `llmc docs quickstart`
Display the quickstart guide.

```bash
llmc docs quickstart
```

---

### `llmc docs userguide`
Display the user guide.

```bash
llmc docs userguide
```

---

## RUTA Commands

### `llmc usertest init`
Initialize RUTA artifacts directory.

```bash
llmc usertest init
```

---

### `llmc usertest run`
Run a user test scenario.

```bash
# Run by scenario ID
llmc usertest run my_scenario

# Run by path
llmc usertest run tests/usertests/scenario.yaml

# Manual mode
llmc usertest run my_scenario --manual
```

**Options:**
- `--suite TAG` - Test suite tag
- `--manual` - Run in manual mode (no agent)

---

## Workflows

### Initial Setup

```bash
cd /path/to/your/project
llmc init
llmc debug index
llmc service repo add .
llmc service start
llmc tui
```

### Daily Development

```bash
# After making changes
llmc debug sync --since HEAD~1

# Search for something
llmc analytics search "authentication"

# Check service health
llmc service status
```

### Troubleshooting

```bash
# Check RAG health
llmc debug doctor --verbose

# View service logs
llmc service logs --follow

# Rebuild index
llmc debug index

# Rebuild graph
llmc debug graph
```

---

## Migration from Previous CLI

| Previous Command | New Command |
|:-----------------|:------------|
| `llmc search` | `llmc analytics search` |
| `llmc stats` | `llmc analytics stats` |
| `llmc benchmark` | `llmc analytics benchmark` |
| `llmc nav where-used` | `llmc analytics where-used` |
| `llmc nav lineage` | `llmc analytics lineage` |
| `llmc index` | `llmc debug index` |
| `llmc doctor` | `llmc debug doctor` |
| `llmc sync` | `llmc debug sync` |
| `llmc enrich` | `llmc debug enrich` |
| `llmc embed` | `llmc debug embed` |
| `llmc graph` | `llmc debug graph` |
| `llmc plan` | `llmc debug plan` |
| `llmc inspect` | `llmc debug inspect` |
| `llmc export` | `llmc debug export` |
| `llmc enrich-status` | `llmc debug enrich-status` |
| `llmc docs generate` | `llmc docs generate` |
| `llmc docs status` | `llmc docs status` |

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

Run `llmc debug index` first to create the index.

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

- [SDD: Unified CLI v2](../planning/sdd/SDD_Unified_CLI_v2.md) - Design document
- [AGENTS.md](../../AGENTS.md) - Agent protocols and workflows
- [ROADMAP.md](../roadmap.md) - Project roadmap
