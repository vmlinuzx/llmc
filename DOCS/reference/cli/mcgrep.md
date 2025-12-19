# mcgrep

Semantic grep with RAG context

**Module:** `llmc.mcgrep`

## Usage

```text
                                       
 Usage: mcgrep [OPTIONS] COMMAND       
 [ARGS]...                             
                                       
 Semantic grep for code. Private.      
 Local. No cloud.                      
                                       
╭─ Options ───────────────────────────╮
│ --help          Show this message   │
│                 and exit.           │
╰─────────────────────────────────────╯
╭─ Commands ──────────────────────────╮
│ search   Semantic search over your  │
│          codebase.                  │
│ watch    Start background indexer   │
│          (alias for 'llmc service   │
│          start').                   │
│ status   Check index health and     │
│          freshness.                 │
│ init     Register the current       │
│          directory with LLMC.       │
│ stop     Stop the background        │
│          indexer.                   │
╰─────────────────────────────────────╯

```

## Search examples

```bash
mcgrep "router"                          # Compact file list + span line ranges
mcgrep "router" --extract 10 --context 3 # Print code for top spans (thin context)
mcgrep "router" --expand 2               # Print full content for top files (thick context)
```
