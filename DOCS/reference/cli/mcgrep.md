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
