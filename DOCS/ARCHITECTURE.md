# LLMC Architecture

This document provides a high-level overview of the LLMC codebase architecture, data flows, and key components.

## Package Structure

```
llmc/                      # Core CLI application
├── main.py                # Typer CLI entry point (`llmc-cli`)
├── commands/              # CLI subcommand modules
│   ├── docs.py            # `llmc docs generate/status`
│   ├── repo_*.py          # `llmc repo add/validate`
│   └── ...
├── docgen/                # Documentation generation
│   ├── orchestrator.py    # SHA-gated doc generation
│   └── config.py          # Docgen configuration
├── security.py            # Path validation (PathSecurityError, normalize_path)
└── te/                    # Template engine (Claude Code style)

llmc_mcp/                  # MCP Server implementation
├── server.py              # Main MCP server with tool handlers
├── cli.py                 # `llmc-mcp` CLI entry point
├── daemon.py              # Daemon management (pidfiles, signals)
├── transport/             # Transport layers
│   ├── http_server.py     # HTTP/SSE transport
│   └── auth.py            # API key authentication
└── tools/                 # MCP tool implementations
    └── code_exec.py       # Code execution sandbox

llmc_agent/                # Agentic chat interface
├── cli.py                 # `bx` / `llmc-chat` entry point
├── agent.py               # Main agent loop
├── backends/              # LLM provider backends
│   └── ollama.py          # Ollama API client
└── prompt.py              # System prompts

tools/rag/                 # RAG indexing and search
├── service.py             # Background enrichment daemon
├── database.py            # SQLite schema and operations
├── indexer.py             # Code span extraction
├── inspector.py           # Entity inspection
├── graph_store.py         # Schema graph store (entities + relations)
├── graph/                 # Graph edge types and filtering
├── schema.py              # SchemaGraph data structures
├── enrichment/            # Query-time enrichment
│   └── __init__.py        # HybridRetriever, QueryAnalyzer
├── enrichment_pipeline.py # LLM enrichment orchestration
├── backends/              # Enrichment backends
│   └── ollama_backend.py  # Ollama enrichment adapter
├── search/                # Vector search
│   └── __init__.py        # Hybrid BM25 + embedding search
├── extractors/            # Language-specific extractors
│   └── techdocs.py        # Markdown/RST heading-aware chunking
└── config.py              # RAG configuration loading

tools/rag_nav/             # Navigation and tool handlers
├── tool_handlers.py       # MCP tool implementations
├── gateway.py             # Route resolution
└── models.py              # IndexStatus, etc.
```

## Data Flow

### 1. Indexing (`llmc index`)

```
Source Files
    │
    ▼
┌─────────────────┐     ┌──────────────────┐
│   Indexer       │────>│   Database       │
│  (tree-sitter)  │     │   (SQLite)       │
└─────────────────┘     │                  │
                        │ • files          │
                        │ • spans          │
                        │ • embeddings     │
                        │ • enrichments    │
                        └──────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   SchemaGraph    │
                        │  (.llmc/rag_     │
                        │   graph.json)    │
                        └──────────────────┘
```

### 2. Enrichment (`llmc service start`)

```
┌─────────────────┐     ┌──────────────────┐
│  Service Loop   │────>│   Ollama         │
│  (service.py)   │<────│   (7b/14b/32b)   │
└─────────────────┘     └──────────────────┘
        │
        ▼
┌─────────────────┐
│ EnrichmentPipeline │
│   • summary     │
│   • inputs      │
│   • outputs     │
│   • side_effects│
│   • pitfalls    │
└─────────────────┘
        │
        ▼
    Database
  (enrichments)
```

### 3. Search (`rag_search` MCP tool)

```
Query ──> ┌──────────────────────────────────┐
          │         Hybrid Search            │
          │                                  │
          │  ┌─────────┐    ┌─────────────┐  │
          │  │  FTS5   │    │  Embeddings │  │
          │  │ (BM25)  │    │  (Jina)     │  │
          │  └────┬────┘    └──────┬──────┘  │
          │       └──────┬─────────┘         │
          │              ▼                   │
          │       ┌────────────┐             │
          │       │  Reranker  │             │
          │       │  (weights) │             │
          │       └─────┬──────┘             │
          │             ▼                    │
          │    Enriched Results              │
          └──────────────────────────────────┘
```

### 4. MCP Integration

```
┌─────────────────┐     ┌──────────────────┐
│  Claude/LLM     │◄───►│  MCP Server      │
│                 │     │  (llmc-mcp)      │
└─────────────────┘     │                  │
                        │ Tools:           │
                        │ • rag_search     │
                        │ • rag_inspect    │
                        │ • rag_where_used │
                        │ • rag_lineage    │
                        │ • read_file      │
                        │ • write_file     │
                        │ • run_cmd        │
                        └──────────────────┘
```

## Configuration

All configuration lives in `llmc.toml` at the repository root:

```toml
[repository]
domain = "code"  # or "tech_docs", "legal", "medical", "mixed"

[enrichment]
enabled = true
model = "qwen3:14b"  # Primary enrichment model
fallback_model = "qwen2.5:7b"  # Cheaper fallback

[embeddings]
model = "jina/jina-embeddings-v3"
dim = 1024

[routing]
# Route queries to appropriate indices

[docs.docgen]
enabled = true
backend = "stub"  # or "llm" (future)
```

## Key Design Decisions

### SQLite over Vector DBs
We use SQLite + FTS5 for text search and a simple embeddings table for vector search. This keeps the stack simple, portable, and avoids external dependencies (no ChromaDB, Pinecone, etc. in the critical path).

### Local-First Enrichment
Enrichment runs on local Ollama models to avoid API costs. The tiered cascade (7b → 14b → 32b) balances speed and quality.

### Schema Graph
The schema graph captures code structure (classes, functions, calls, extends) separately from content. This enables relationship-aware search and navigation.

### MCP Mode Flexibility
- **Classic mode**: All 27 tools exposed (~10KB token overhead)
- **Hybrid mode**: 6-7 promoted tools (~2.5KB), trusted environment
- **Code exec mode**: 4 bootstrap tools (~1.9KB), Docker isolation (deprecated)

## Security Boundaries

### Path Traversal Protection
All file operations go through `llmc/security.py:normalize_path()` which:
- Rejects null bytes
- Validates paths stay within repository root
- Blocks `../` traversal attempts

### MCP Tool Trust Model
MCP Hybrid Mode assumes the user trusts the environment. Write tools (`write_file`, `run_cmd`) have no additional sandboxing beyond `allowed_roots` configuration.

For untrusted code, the original design called for Docker isolation, but this proved impractical for typical LLMC usage.

## Module Dependencies

```
llmc (CLI)
├── llmc.docgen
├── llmc.security
└── tools.rag

llmc_mcp (MCP Server)
├── tools.rag
├── tools.rag_nav
└── llmc_mcp.tools.code_exec

llmc_agent (Chat)
├── llmc_agent.backends.ollama
└── tools.rag (optional, for context)

tools.rag
├── tools.rag.graph_store  # Schema graph
├── tools.rag.graph/       # Edge types
├── tools.rag.enrichment   # Query enrichment
└── tools.rag.search       # Hybrid search

tools.rag_nav
├── tools.rag (via absolute imports)
└── (avoids circular imports)
```

## Testing

Tests live in `tests/` and can be run with:

```bash
# Core tests (no external deps)
pytest tests/test_fts5*.py tests/test_graph*.py tests/test_enrichment*.py

# All tests (requires .venv with all deps)
pytest tests/

# MCP tests (requires mcp package)
pytest tests/test_rmta*.py tests/test_mcp*.py
```

## Entry Points

| Command | Entry Point | Package |
|---------|-------------|---------|
| `llmc-cli` | `llmc.main:app` | llmc |
| `llmc-mcp` | `llmc_mcp.cli:main` | llmc_mcp |
| `bx` / `llmc-chat` | `llmc_agent.cli:main` | llmc_agent |
| `te` | `llmc.te.cli:main` | llmc.te |
| `mcgrep` | `llmc.mcgrep:main` | llmc |

## Related Documentation

- [Roadmap](planning/roadmap.md) - Current and planned work
- [CLI Reference](user-guide/cli-reference.md) - Command documentation
- [MCP Hybrid Mode SDD](planning/SDD_MCP_Hybrid_Mode.md) - MCP architecture details
- [Domain RAG Tech Docs](legacy/SDD_Domain_RAG_Tech_Docs.md) - Tech docs support
