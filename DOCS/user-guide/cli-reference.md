# LLMC Unified CLI Reference

**Version:** 0.6.0  
**Last Updated:** 2025-12-04

---

## Installation

```bash
cd /path/to/llmc
pip install -e .
```

This installs the `llmc-cli` command globally.

---

## Command Structure Overview

The CLI is organized into logical groups for discoverability:

```
llmc-cli
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
├── repo              # Repository management
│   ├── register      # Full setup (init+index+daemon)
│   ├── rm            # Unregister
│   ├── clean         # Wipe artifacts
│   ├── nukerag       # Clear enrichment
│   └── validate      # Check config
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
├── chat              # AI Coding Assistant
│
└── test              # Testing tools
    └── mcp           # MCP compliance testing
```

---

## Quick Start

```bash
# Initialize a new repository
llmc-cli init

# Start the RAG service
llmc-cli service repo add .
llmc-cli service start

# Search semantically
llmc-cli analytics search "how does authentication work?"

# View stats
llmc-cli analytics stats

# Launch TUI
llmc-cli tui
```

---

## Core Commands

### `llmc-cli init`
Bootstrap `.llmc/` workspace and configuration.

```bash
llmc-cli init
```

Creates:
- `.llmc/` directory
- `llmc.toml` configuration file
- Empty database schema
- Log directory

---

## Repository Management

### `llmc-cli repo register`
Register a repository with LLMC. This is the primary setup command.

```bash
# Register current directory
llmc-cli repo register .

# Register specific path with interactive wizard
llmc-cli repo register /path/to/repo --interactive
```

This command:
1. Creates `.llmc/` workspace
2. Initializes the database
3. Indexes all source files
4. Registers with the daemon for enrichment

---

### `llmc-cli repo rm`
Unregister a repository from the daemon (keeps local `.llmc/` data).

```bash
llmc-cli repo rm /path/to/repo
```

---

### `llmc-cli repo clean`
Completely remove LLMC from a repository (wipes `.llmc/` and `.rag/`).

```bash
# Dry run
llmc-cli repo clean .

# Force delete
llmc-cli repo clean . --force
```

---

### `llmc-cli repo validate`
Validate repository configuration and connectivity.

```bash
llmc-cli repo validate .
```

---

### `llmc-cli config`
Launch the interactive enrichment configuration TUI.

```bash
llmc-cli config
```

---

### `llmc-cli tui`
Launch the interactive TUI dashboard.

```bash
llmc-cli tui
```

Features:
- Live system metrics
- Service status monitoring
- Code search interface
- RAG health diagnostics
- Configuration editor

---

### `llmc-cli monitor`
Monitor service logs (alias for `llmc-cli service logs -f`).

```bash
llmc-cli monitor
```

---

### `llmc-cli chat`
AI coding assistant with RAG-powered context.

```bash
llmc-cli chat "Where is the routing logic?"
llmc-cli chat -n "New session"
llmc-cli chat -r  # Recall last session
```

---

### `llmc-cli --version`
Show version information and repository status.

```bash
llmc-cli --version
# Output:
# LLMC v0.6.0
# Root: /home/user/src/myproject
# Config: Found
```

---

## Analytics Commands

### `llmc-cli analytics search`
Semantic search over indexed code.

```bash
# Basic search
llmc-cli analytics search "JWT verification"

# Limit results
llmc-cli analytics search "database connection" --limit 20

# JSON output
llmc-cli analytics search "error handling" --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Output as JSON

---

### `llmc-cli analytics stats`
Print summary statistics for the current index.

```bash
# Human-readable stats
llmc-cli analytics stats

# JSON output
llmc-cli analytics stats --json
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

### `llmc-cli analytics benchmark`
Run embedding quality benchmark.

```bash
# Run benchmark
llmc-cli analytics benchmark

# JSON output
llmc-cli analytics benchmark --json

# Adjust thresholds
llmc-cli analytics benchmark --top1-threshold 0.8 --margin-threshold 0.15
```

**Options:**
- `--json` - Emit metrics as JSON
- `--top1-threshold FLOAT` - Minimum top-1 accuracy (default: 0.75)
- `--margin-threshold FLOAT` - Minimum margin (default: 0.1)

---

### `llmc-cli analytics where-used`
Find where a symbol is used.

```bash
# Find usages
llmc-cli analytics where-used search_spans

# Limit results
llmc-cli analytics where-used Database --limit 50

# JSON output
llmc-cli analytics where-used index_repo --json
```

**Options:**
- `--limit N` - Max results (default: 10)
- `--json` - Emit JSON output

---

### `llmc-cli analytics lineage`
Show symbol lineage (dependencies).

```bash
# Show lineage
llmc-cli analytics lineage search_spans

# Deeper traversal
llmc-cli analytics lineage Database --depth 5

# JSON output
llmc-cli analytics lineage index_repo --json
```

**Options:**
- `--depth N` - Max depth to traverse (default: 2)
- `--json` - Emit JSON output

---

## Debug Commands

### `llmc-cli debug index`
Index the repository (full or incremental).

```bash
# Full index
llmc-cli debug index

# Incremental (since commit)
llmc-cli debug index --since HEAD~10

# Skip JSONL export
llmc-cli debug index --no-export
```

**Options:**
- `--since SHA` - Only parse files changed since commit
- `--no-export` - Skip JSONL span export

---

### `llmc-cli debug doctor`
Diagnose RAG health and identify issues.

```bash
# Basic health check
llmc-cli debug doctor

# Verbose output
llmc-cli debug doctor --verbose
```

---

### `llmc-cli debug sync`
Incrementally update spans for selected files.

```bash
# Sync specific files
llmc-cli debug sync --path llmc/rag/search.py --path llmc/rag/indexer.py

# Sync files changed since commit
llmc-cli debug sync --since HEAD~5

# Read paths from stdin
git diff --name-only HEAD~10 | llmc-cli debug sync --stdin
```

**Options:**
- `--path PATH` - Specific file paths (can be repeated)
- `--since SHA` - Sync files changed since commit
- `--stdin` - Read paths from stdin

---

### `llmc-cli debug enrich`
Run LLM-based enrichment on spans.

```bash
# Dry run (preview work)
llmc-cli debug enrich --dry-run

# Enrich 50 spans
llmc-cli debug enrich --limit 50

# Use specific model
llmc-cli debug enrich --model gpt-4 --limit 10

# Skip recently changed files
llmc-cli debug enrich --cooldown 300
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

### `llmc-cli debug embed`
Generate embeddings for spans.

```bash
# Dry run
llmc-cli debug embed --dry-run

# Generate embeddings
llmc-cli debug embed --limit 100

# Use specific model
llmc-cli debug embed --model sentence-transformers/all-MiniLM-L6-v2

# Specify dimension
llmc-cli debug embed --dim 384
```

**Options:**
- `--limit N` - Max spans (default: 10)
- `--dry-run` - Preview without generating
- `--model NAME` - Embedding model (default: auto)
- `--dim N` - Embedding dimension (default: 0 = auto)

---

### `llmc-cli debug graph`
Build a schema graph for the repository.

```bash
# Build graph (requires enrichment)
llmc-cli debug graph

# Allow empty enrichment
llmc-cli debug graph --no-require-enrichment

# Custom output path
llmc-cli debug graph --output /tmp/my_graph.json
```

**Options:**
- `--require-enrichment / --no-require-enrichment` - Require enrichment data (default: true)
- `--output PATH` - Output path (default: .llmc/rag_graph.json)

---

### `llmc-cli debug plan`
Generate a retrieval plan for a query.

```bash
# Generate plan
llmc-cli debug plan "Where do we validate user input?"

# Adjust confidence threshold
llmc-cli debug plan "authentication flow" --min-confidence 0.7

# More results
llmc-cli debug plan "error handling" --limit 100
```

**Options:**
- `--limit N` - Max files/spans (default: 50)
- `--min-confidence FLOAT` - Minimum confidence (default: 0.6)

---

### `llmc-cli debug inspect`
Deep dive into a file or symbol with graph context.

```bash
# Inspect by symbol
llmc-cli debug inspect --symbol llmc.rag.search.search_spans

# Inspect by file path
llmc-cli debug inspect --path llmc/rag/search.py

# Include full source
llmc-cli debug inspect --path llmc/rag/search.py --full

# Focus on specific line
llmc-cli debug inspect --path llmc/rag/search.py --line 42
```

**Options:**
- `--symbol, -s` - Symbol to inspect
- `--path, -p` - File path
- `--line, -l` - Line number
- `--full` - Include full source code

---

### `llmc-cli debug export`
Export all RAG data to tar.gz archive.

```bash
# Export with auto-generated name
llmc-cli debug export

# Custom output path
llmc-cli debug export --output /tmp/rag_backup.tar.gz
```

**Options:**
- `--output, -o PATH` - Output archive path

---

### `llmc-cli debug enrich-status`
Show enrichment runner metrics and code-first status.

```bash
# Human-readable output
llmc-cli debug enrich-status

# JSON output
llmc-cli debug enrich-status --json
```

---

### `llmc-cli docs generate`
Generate documentation for repository files.

```bash
llmc-cli docs generate
```

---

### `llmc-cli docs status`
Show documentation generation status.

```bash
llmc-cli docs status
```

---

## Service Management

### `llmc-cli service start`
Start the RAG service daemon.

```bash
# Start with default interval (180s)
llmc-cli service start

# Custom interval
llmc-cli service start --interval 300
```

**Options:**
- `--interval N` - Enrichment cycle interval in seconds (default: 180)

**Prerequisites:**
- At least one repository registered (`llmc-cli service repo add`)
- Systemd available

---

### `llmc-cli service stop`
Stop the RAG service daemon.

```bash
llmc-cli service stop
```

---

### `llmc-cli service restart`
Restart the RAG service daemon.

```bash
# Restart with current settings
llmc-cli service restart

# Update interval on restart
llmc-cli service restart --interval 120
```

**Options:**
- `--interval N` - Update enrichment interval

---

### `llmc-cli service status`
Show service status and registered repos.

```bash
llmc-cli service status
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

### `llmc-cli service logs`
View service logs via journalctl.

```bash
# View last 50 lines
llmc-cli service logs

# View last 100 lines
llmc-cli service logs --lines 100

# Follow logs (like tail -f)
llmc-cli service logs --follow
```

**Options:**
- `--follow, -f` - Follow log output
- `--lines, -n N` - Number of lines to show (default: 50)

---

### `llmc-cli service enable`
Enable service to start on user login.

```bash
llmc-cli service enable
```

---

### `llmc-cli service disable`
Disable service from starting on user login.

```bash
llmc-cli service disable
```

---

### `llmc-cli service repo add`
Register a repository for enrichment.

```bash
llmc-cli service repo add /path/to/repo
```

---

### `llmc-cli service repo remove`
Unregister a repository.

```bash
llmc-cli service repo remove /path/to/repo
```

---

### `llmc-cli service repo list`
List all registered repositories.

```bash
llmc-cli service repo list
```

**Output:**
```
Registered repositories (2):

1. /home/user/src/llmc
2. /home/user/src/myproject
```

---

## Documentation Commands

### `llmc-cli docs readme`
Display the LLMC README.

```bash
llmc-cli docs readme
```

---

### `llmc-cli docs quickstart`
Display the quickstart guide.

```bash
llmc-cli docs quickstart
```

---

### `llmc-cli docs userguide`
Display the user guide.

```bash
llmc-cli docs userguide
```

---


## Workflows

### Initial Setup

```bash
cd /path/to/your/project
llmc-cli init
llmc-cli service start
llmc-cli repo register
llmc-cli tui
```

### Daily Development

```bash
# After making changes
llmc-cli debug sync --since HEAD~1

# Search for something
llmc-cli analytics search "authentication"

# Check service health
llmc-cli service status
```

### Troubleshooting

```bash
# Check RAG health
llmc-cli debug doctor --verbose

# View service logs
llmc-cli service logs --follow

# Rebuild index
llmc-cli debug index

# Rebuild graph
llmc-cli debug graph
```

---

## Migration from Previous CLI

| Previous Command | New Command |
|:-----------------|:------------|
| `llmc search` | `llmc-cli analytics search` |
| `llmc stats` | `llmc-cli analytics stats` |
| `llmc benchmark` | `llmc-cli analytics benchmark` |
| `llmc nav where-used` | `llmc-cli analytics where-used` |
| `llmc nav lineage` | `llmc-cli analytics lineage` |
| `llmc index` | `llmc-cli debug index` |
| `llmc doctor` | `llmc-cli debug doctor` |
| `llmc sync` | `llmc-cli debug sync` |
| `llmc enrich` | `llmc-cli debug enrich` |
| `llmc embed` | `llmc-cli debug embed` |
| `llmc graph` | `llmc-cli debug graph` |
| `llmc plan` | `llmc-cli debug plan` |
| `llmc inspect` | `llmc-cli debug inspect` |
| `llmc export` | `llmc-cli debug export` |
| `llmc enrich-status` | `llmc-cli debug enrich-status` |
| `llmc docs generate` | `llmc-cli docs generate` |
| `llmc docs status` | `llmc-cli docs status` |

---

## Shell Completion

Install shell completion for better UX:

```bash
# Bash
llmc-cli --install-completion bash

# Zsh
llmc-cli --install-completion zsh

# Fish
llmc-cli --install-completion fish
```

---

## Troubleshooting

### "No index database found"

Run `llmc-cli debug index` first to create the index.

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
llmc-cli service status
llmc-cli service logs --lines 100
```

---

## See Also

- [AGENTS.md](../../AGENTS.md) - Agent protocols and workflows
- [ROADMAP.md](../ROADMAP.md) - Project roadmap
