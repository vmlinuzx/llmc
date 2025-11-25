# Changelog

All notable changes to LLMC will be documented in this file.

## [0.5.0] - "Token Umami" - 2025-11-25

### Purple Flavor: **Token Umami**

Initial public release of LLMC. This is a working, tested system that achieves 60-95% token cost reduction through intelligent routing, RAG-first workflows, and local model optimization.

### Added
- Complete RAG system with SQLite-backed indexing and full-text search
- Schema-aware GraphRAG for relationship-based code navigation
- Intelligent LLM routing (local → mid-tier → premium) with cost optimization
- Multi-model enrichment pipeline supporting local and remote backends
- Daemon-based background indexing and enrichment workers
- Freshness-aware context gateway preventing stale RAG results
- TUI for monitoring and interactive search
- Desktop Commander and MCP integration for agent workflows
- Comprehensive test suite with 100+ tests
- Production-ready enrichment for Python repositories
- CLI tools: `llmc-rag-service`, `llmc-rag-repo`, `llmc-rag-daemon`

### What Works
- Local RAG indexing keeps repos searchable without LLM calls
- Three-tier routing achieves massive cost savings (typical $300/month → $25/month)
- Semantic chunking via AST produces high-quality code spans
- Enrichment metadata (summaries, tags, evidence) improves search relevance
- Anti-stomp coordination for parallel agent work
- Freshness tracking prevents context poisoning from stale data

### Known Limitations
- Python-first: GraphRAG strongest for Python, other languages use stubs
- Line number changes force re-enrichment of downstream spans (solution designed, not implemented)
- TUI still under active polish
- Some experimental features (web server) not production-ready

### Documentation
- Comprehensive README with capabilities and architecture
- AGENTS.md for LLM agent behavioral contracts
- CONTRACTS.md for environment and policy rules
- Detailed ROADMAP.md with phased development plan
- User guides and design docs in DOCS/

## Unreleased

- Working on tool result compression feature (Anthropic whitepaper implementation)

