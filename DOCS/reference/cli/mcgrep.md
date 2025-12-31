# mcgrep

Semantic grep with RAG context

**Module:** `llmc.mcgrep`

## Usage

```text

 Usage: python -m llmc.mcgrep [OPTIONS] COMMAND [ARGS]...

 Semantic grep for code. Private. Local. No cloud.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ search   Semantic search over your codebase.                                 │
│ watch    Start background indexer (alias for 'llmc service start').          │
│ status   Check index health and freshness.                                   │
│ init     Register the current directory with LLMC.                           │
│ stop     Stop the background indexer.                                        │
╰──────────────────────────────────────────────────────────────────────────────╯

```

## Search Examples

```bash
mcgrep "where is auth handled?"
mcgrep "database connection" src/
mcgrep -n 20 "error handling"
mcgrep "router" --extract 10 --context 3
mcgrep watch                    # Start background indexer
mcgrep status                   # Check index health
```
