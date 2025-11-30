# Changelog

All notable changes to LLMC will be documented in this file.

## [0.5.5] - "Modular Mojo" - 2025-11-28

### Purple Flavor: **Modular Mojo**

This release introduces a major architectural upgrade to the embedding system, making LLMC more flexible and configurable than ever. It also includes significant hardening of the CLI tools and telemetry system.


### Added
- **Modular Embeddings Architecture:**
- **Currently we only support one profile, but the guts are there for a routing system now**
    - **Profiles:** Define multiple embedding profiles (e.g., `code` using local SentenceTransformers, `docs` using remote Ollama) in `llmc.toml`.
    - **Provider Abstraction:** Clean separation between `Hash`, `SentenceTransformer`, and `Ollama` providers.
    - **Configuration:** New `[embeddings.profiles.*]` section in `llmc.toml` allows granular control over models, dimensions, and provider-specific settings.
    - **Migration:** Automatic database schema migration to support profile-aware embedding storage.
- **Live Integration Tests:** Added `tests/test_ollama_live.py` to verify real-world connectivity and data fidelity with Ollama endpoints.
- **Data Integrity Tests:** Added `tests/test_te_enrichment_manual.py` to ensure binary storage of vectors is bit-perfect and profiles are correctly isolated.
- **More TUI Functionality:** Added screen 7, RAG Doctor, this allows the monitoring of embeddings health, and perform corrective actions, and eventualy will do much more.  Also made logs spam a bit more with embeddings health updates, and who doesn't love more log spam.

### Changed
- **TE this system is beign designed to remove tool definitions from MCP servers aleviating the overhead that comes with that**
- **Telemetry Hardening Alpha Testing:** The Tool Envelope (TE) telemetry now consistently uses `.llmc/te_telemetry.db` (SQLite) instead of a mix of JSONL and DB, preventing data loss and configuration confusion.
- **CLI Improvements:**
    - `llmc-rag` now accepts user queries directly as arguments (e.g., `llmc-rag "how does X work?"`) instead of defaulting to "ping".
    - `llmc-rag-repo snapshot` no longer crashes due to missing imports.
- **Code Quality:** Massive linting cleanup (1000+ issues fixed) across `llmcwrapper`, `llmc/te`, and core tools.

### Fixed
- Critical crash in `llmc-rag-repo snapshot` caused by undefined `SafeFS`.
- `llmc-rag` CLI ignoring user input.
- Telemetry configuration mismatch between `llmc.toml` and internal code.

## [0.5.0] - "Token Umami" - 2025-11-25

### Purple Flavor: **Breakfast in Bed**

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