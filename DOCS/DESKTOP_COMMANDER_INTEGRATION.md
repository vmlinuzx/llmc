# Desktop Commander Integration

## What This Is

LLMC integrates with Desktop Commander to give Claude (or any MCP-compatible AI) the ability to search and navigate your codebase using RAG (Retrieval-Augmented Generation) instead of reading entire files. This dramatically reduces token usage and improves response quality by providing only the relevant code context.

## Why This Matters

**Without LLMC:**
- Claude reads entire files (thousands of tokens per file)
- Context window fills quickly
- Loses context across long sessions
- Slower responses due to token processing
- Higher costs

**With LLMC:**
- Claude queries the RAG index for relevant code spans
- Gets 5-10 targeted results (~200-500 tokens total)
- Maintains focus on relevant code
- Faster responses
- 60-95% token reduction in typical sessions

**Example:**
- Old way: "Read these 5 files (15,000 tokens) and find the authentication logic"
- New way: "Search RAG for 'authentication logic' → Get 3 relevant functions (800 tokens)"

## How It Works

1. **Index Phase** (runs in background):
   - LLMC daemon scans your repo
   - Chunks code into logical spans (functions, classes)
   - Generates embeddings for semantic search
   - Enriches spans with AI-generated summaries
   - Builds schema graph (entities and relationships)

2. **Query Phase** (when Claude needs context):
   - Claude searches the RAG index with natural language
   - Gets back ranked, relevant code spans
   - Includes summaries, line numbers, file paths
   - No need to read entire files

3. **Freshness Checking**:
   - System tracks git commits and file modifications
   - Returns stale warnings if index is out of date
   - Falls back to filesystem if RAG results unreliable

## Available Tools

Desktop Commander exposes these RAG capabilities to Claude through the standard CLI.

### Core Search Tools

**1. Semantic Search (`search`)**

Find code spans using natural language queries.

```bash
python3 -m tools.rag.cli search "JWT validation logic" --limit 5 --json
```

**Returns:** JSON array with:
- File path and line range
- Function/class name
- Similarity score (0-1)
- AI-generated summary of what the code does

**When to use:** Quick lookups for specific concepts or patterns.

---

**2. Structured Planning (`plan`)**

Generate a retrieval plan with confidence scoring and symbol matching.

```bash
python3 -m tools.rag.cli plan "How does the authentication middleware work?"
```

**Returns:** Structured plan including:
- Detected intent from query
- Top matching symbols with scores
- Relevant spans with rationales
- Overall confidence score
- Recommendation to broaden/narrow search

**When to use:** Complex queries requiring multiple related code sections.

---

**3. Freshness-Aware Search (`nav search`)**

Search with automatic freshness checking and filesystem fallback.

```bash
python3 -m tools.rag.cli nav search "schema enrichment" /home/user/src/llmc
```

**Returns:** Search results plus metadata:
- Whether results are fresh or stale
- Last indexed commit
- Recommendation to reindex if stale

**When to use:** When you need to trust that results reflect current code state.

### Navigation Tools

**4. Where-Used Analysis (`nav where-used`)**

Find all places a symbol is used in the codebase.

```bash
python3 -m tools.rag.cli nav where-used "SchemaGraph" /home/user/src/llmc
```

**Returns:** List of usage sites with context.

**When to use:** Understanding impact of changes, finding all callers.

---

**5. Call Graph Lineage (`nav lineage`)**

Analyze call graph relationships (who calls what).

```bash
python3 -m tools.rag.cli nav lineage "process_request" /home/user/src/llmc --direction upstream
```

**Parameters:**
- `upstream`: Find who calls this function (callers)
- `downstream`: Find what this function calls (callees)

**When to use:** Understanding data flow, tracing execution paths.

### Maintenance Tools

**6. Index Status (`nav status`)**

Check health and freshness of the RAG index.

```bash
python3 -m tools.rag.cli nav status /home/user/src/llmc
```

**Returns:** Index state (FRESH/STALE), last indexed commit, timestamps.

---

**7. Rebuild Graph (`graph`)**

Rebuild the schema graph and index (use if stale).

```bash
python3 -m tools.rag.cli graph /home/user/src/llmc
```

**Warning:** Resource intensive, runs in foreground.

---

**8. Index Statistics (`stats`)**

View index health and coverage.

```bash
python3 -m tools.rag.cli stats --json
```

**Returns:** File count, span count, embedding coverage, enrichment coverage.

---

**9. Health Check (`doctor`)**

Run diagnostics on the RAG system.

```bash
python3 -m tools.rag.cli doctor
```

**Returns:** Issues with index, missing files, configuration problems.

## How Claude Uses These Tools

When you ask Claude questions about your codebase, Claude automatically:

1. **Determines what it needs** - "I need to find authentication logic"
2. **Chooses the right tool** - Uses `search` for quick lookup or `plan` for complex queries
3. **Gets targeted results** - Receives only relevant code spans
4. **Answers your question** - Using precise context instead of entire files

**Example interaction:**

**You:** "How does the enrichment pipeline work?"

**Claude's process:**
1. Calls `plan "enrichment pipeline"`
2. Gets back 5 relevant spans with confidence scores
3. Reads summaries and code context
4. Explains how enrichment works
5. Total tokens: ~1,200 instead of ~15,000

## Schema-Aware Features

LLMC builds a **graph** of your codebase:

- **Entities**: Functions, classes, variables, modules
- **Relationships**: Calls, imports, extends, uses
- **Graph traversal**: Find related code 1-2 hops away

This means Claude can understand:
- "Who calls this function?" (upstream navigation)
- "What does this function call?" (downstream navigation)
- "What's related to this code?" (neighbor expansion)

Think of it as **RAG with structural awareness** - not just semantic similarity, but understanding how code actually connects.

## Automatic Background Maintenance

The LLMC daemon (`llmc-rag-daemon`) runs in the background to keep indexes fresh:

1. **Watches git commits** - Detects when you change code
2. **Incremental updates** - Only reprocesses changed files
3. **Scheduled enrichment** - Runs AI enrichment during downtime
4. **Local inference** - Uses your local GPU for enrichment (overnight/idle time)

This means the index stays current without you doing anything.

## Configuration

LLMC auto-detects repo roots via git. You can override with:

**Environment variables:**
```bash
export LLMC_REPO_ROOT=/home/user/src/myproject
```

**Command flags:**
```bash
python3 -m tools.rag.cli search "query" --repo /path/to/repo
```

**Daemon configuration:**
- Location: `~/.llmc/rag-daemon.yml`
- Controls: tick interval, enrichment batch size, model selection

## Performance Characteristics

**Query latency:**
- Simple search: 100-300ms
- Structured plan: 300-500ms
- Where-used: 50-200ms
- Lineage: 200-400ms

**Token savings:**
- Typical query: 70-95% reduction vs. full file reads
- Long sessions: Prevents context window exhaustion
- Complex projects: Makes large codebases navigable

**Index overhead:**
- Disk: ~10-20MB per 200 files
- Memory: <100MB for typical index
- CPU: Background enrichment uses local GPU when idle

## Limitations

**Current focus:**
- **Python-first**: Schema extraction strongest for Python
- **Other languages**: Basic support (AST parsing for structure, limited relationships)
- **Binary files**: Not indexed
- **Generated code**: Can pollute index (configure exclusions in `llmc.toml`)

**Freshness:**
- Index updates incrementally but not instantly
- Check status if working on rapidly changing code
- Manual reindex available if needed

## Troubleshooting

**"No index database found"**
→ Run `python3 -m tools.rag.cli index` to create initial index

**"Index is stale"**
→ Run `llmc-rag-daemon tick` for manual refresh or check daemon status

**Low confidence scores in plan results**
→ Try lowering `--min-score` (default 0.4) to see more candidates

**No results for recent changes**
→ Check `nav status` - may need to wait for daemon cycle or force update

**High token usage still occurring**
→ Verify Claude is actually calling RAG tools (check logs in `logs/run_ledger.log`)

## Integration with Other Tools

**Desktop Commander:**
- Native integration through command execution
- No special wrappers needed
- Claude calls RAG CLI directly

**MCP Servers:**
- Can expose LLMC tools via MCP protocol
- Tool manifest can be generated from CLI help output

**Cline/Continue/Aider:**
- Use wrapper scripts in `tools/` directory
- Or call RAG CLI directly from custom prompts

## Next Steps

1. **Verify daemon is running:** `ps aux | grep llmc-rag`
2. **Check index status:** `python3 -m tools.rag.cli stats`
3. **Test a search:** `python3 -m tools.rag.cli search "your query" --limit 3`
4. **Watch it work:** Ask Claude questions about your codebase and observe token usage

The system is designed to be invisible - it just makes Claude smarter and cheaper to run on large codebases.
