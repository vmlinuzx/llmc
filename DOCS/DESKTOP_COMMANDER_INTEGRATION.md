# Desktop Commander + Claude RAG Integration

## Overview

LLMC's RAG system is now fully integrated with Desktop Commander and Claude through two simple wrapper scripts that expose schema-enriched retrieval capabilities.

## What's New: Schema Functionality

The RAG system now includes **schema-aware enrichment** with entity-relation graphs:

- **Entities**: Functions, classes, variables, tables
- **Relations**: Calls, uses, reads, writes, extends
- **Graph Traversal**: 1-2 hop neighbor lookups for contextual code discovery
- **Hybrid Retrieval**: Combines vector search with graph traversal

Think of it as RAG with structural awareness - "a sundress with pockets."

## Available Tools

### 1. Simple Vector Search: `dc_rag_query.sh`

Basic semantic search over code spans.

**Usage:**
```bash
./tools/dc_rag_query.sh "JWT validation logic" --limit 5
./tools/dc_rag_query.sh "authentication" --repo /path/to/repo
```

**Returns:** JSON array with:
- `rank`: Result ranking
- `path`: File path
- `symbol`: Function/class name
- `lines`: Line range [start, end]
- `score`: Cosine similarity (0-1)
- `summary`: Human-readable description

**Example Output:**
```json
[
  {
    "rank": 1,
    "span_hash": "sha256:...",
    "path": "tools/rag/schema.py",
    "symbol": "SchemaGraph",
    "kind": "class",
    "lines": [80, 85],
    "score": 0.879,
    "summary": "Complete entity-relation graph for a repository"
  }
]
```

### 2. Schema-Aware Planning: `dc_rag_plan.sh`

Intelligent retrieval planner with symbol matching, confidence scoring, and graph-enriched results.

**Usage:**
```bash
./tools/dc_rag_plan.sh "How does schema enrichment work?"
./tools/dc_rag_plan.sh "JWT validation flow" --limit 10 --min-score 0.5
```

**Returns:** Structured plan with:
- `query`: Original query
- `intent`: Detected intent pattern
- `symbols`: Top matching symbols with scores
- `spans`: Relevant code spans with rationales
- `confidence`: Overall confidence (0-1)
- `fallback_recommended`: Whether to broaden search

**Example Output:**
```json
{
  "query": "How does schema enrichment work with graph traversal?",
  "intent": "schema-enrichment-work-graph",
  "symbols": [
    {
      "name": "SchemaGraph.load",
      "path": "tools/rag/schema.py",
      "score": 16.2
    }
  ],
  "spans": [
    {
      "span_hash": "sha256:...",
      "path": "tools/rag/schema.py",
      "lines": [93, 119],
      "score": 16.2,
      "rationale": [
        "symbol 'SchemaGraph.load' matches 'schema'",
        "path 'tools/rag/schema.py' contains 'schema'",
        "summary mentions 'schema'"
      ]
    }
  ],
  "confidence": 0.802,
  "fallback_recommended": false
}
```

## Integration with Claude

Both wrappers work seamlessly with Claude through Desktop Commander's process execution:

```bash
# From Claude/Desktop Commander
dc_rag_query "authentication middleware" --limit 3
dc_rag_plan "How does the enrichment daemon schedule work?" --no-log
```

### Using from Claude

Claude can call these directly via Desktop Commander:

1. **For quick lookups**: Use `dc_rag_query.sh` for simple semantic search
2. **For complex queries**: Use `dc_rag_plan.sh` for structured retrieval with reasoning
3. **Auto-detection**: Both scripts auto-detect repo root from git or use `--repo` flag

## Direct CLI Usage (Without Wrappers)

You can also use the RAG CLI directly:

```bash
cd ~/src/llmc
source .venv/bin/activate

# Simple search
python3 -m tools.rag.cli search "schema graph" --limit 5 --json

# Structured plan
python3 -m tools.rag.cli plan "How does JWT validation work?"

# View stats
python3 -m tools.rag.cli stats

# Check health
python3 -m tools.rag.cli doctor
```

## Available Commands

Full CLI command reference:

- `index` - Index the repository (full or incremental)
- `sync` - Incrementally update spans for selected files
- `search` - Run cosine-similarity search
- `plan` - Generate structured retrieval plan
- `stats` - Print summary stats
- `embed` - Execute embedding jobs
- `enrich` - Execute enrichment tasks
- `doctor` - Run health checks
- `analytics` - View query analytics
- `benchmark` - Run embedding quality tests
- `export` - Export all RAG data
- `paths` - Show index storage paths

## Environment Variables

Both wrappers support:

- `LLMC_REPO_ROOT` - Override repo detection
- Auto-detection via git (uses `git rev-parse --show-toplevel`)
- Explicit `--repo /path/to/repo` flag

## Current Index Stats

As of last check:
- **Files**: 213
- **Spans**: 1,378
- **Embeddings**: 1,378 (100% coverage)
- **Enrichments**: 1,378 (100% coverage)
- **Estimated tokens saved**: 482,300 tokens (482K)

## Next Steps

### For Production Use:

1. **Add to PATH**: Already done if following README instructions
2. **Register Repos**: Use `llmc-rag-repo add /path/to/repo`
3. **Start Daemon**: Use `llmc-rag-daemon run` for auto-refresh
4. **Query Away**: Use either wrapper from Claude or command line

### For Development:

1. Test queries: Try both wrappers with different query types
2. Check confidence: Look at plan output confidence scores
3. Tune thresholds: Adjust `--min-score` and `--min-confidence`
4. Monitor logs: Check `logs/planner_metrics.jsonl` for insights

## Troubleshooting

### "No index database found"
Run `python3 -m tools.rag.cli index` in the repo first.

### "No .venv found"
Create venv: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[rag]"`

### Low confidence scores
Try `dc_rag_plan` with `--min-score 0.3` to broaden results.

### Stale index
Run `llmc-rag-daemon tick` for manual refresh or `llmc-rag-service start` for automated updates.

## Technical Details

### Schema Extraction

The system extracts:
- **Python**: Functions, classes, methods via AST parsing
- **TypeScript/JavaScript**: Functions, classes, exports
- **Relations**: Function calls, imports, class inheritance

### Enrichment Pipeline

1. Parse code into spans (AST-based)
2. Generate embeddings (sentence-transformers)
3. Extract schema (entities + relations)
4. Build graph (adjacency lists)
5. Enrich with summaries (local Qwen models)

### Hybrid Retrieval

Combines:
- **Vector search**: Semantic similarity via cosine distance
- **Graph traversal**: 1-2 hop neighbor expansion
- **Symbol matching**: Fuzzy name matching with scoring
- **Confidence estimation**: Multi-factor scoring with thresholds

## Performance

- **Query latency**: ~100-300ms for search, ~500ms for plan
- **Index size**: ~10MB for 200 files, 1300 spans
- **Memory**: <100MB for typical index
- **Token savings**: ~350 tokens per span vs. full file context
