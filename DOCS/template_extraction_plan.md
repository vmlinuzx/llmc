# LLM Commander Template Extraction Plan

## Executive Summary

This document outlines the core components of the LLM Commander system that should be extracted for the "living template" - focusing on the essential context management magic that makes this system powerful for LLM orchestration.

## Core Context Management Components to Extract

### 1. RAG System (`tools/rag/` and `scripts/rag/`)

**Status**: ✅ **ESSENTIAL - Include**

**Components:**
- `tools/rag/` - Complete RAG implementation with embeddings, search, indexing
- `scripts/rag/` - RAG orchestration scripts and helpers

**Key Files:**
- `tools/rag/README.md` - RAG system documentation and usage
- `tools/rag/cli.py` - Main RAG CLI interface
- `tools/rag/database.py` - Database operations and schema
- `tools/rag/embeddings.py` - Embedding generation and management
- `tools/rag/indexer.py` - Code indexing and span extraction
- `tools/rag/search.py` - Semantic search implementation
- `tools/rag/utils.py` - Core RAG utilities
- `tools/rag/requirements.txt` - RAG dependencies
- `scripts/rag/setup_rag.sh` - RAG system setup
- `scripts/rag/rag_server.py` - RAG server implementation

**Context Magic**: This is the heart of the context management system - provides local semantic search over codebases with embeddings, incremental indexing, and context retrieval.

### 2. Core Orchestration Scripts (`scripts/` - Core Only)

**Status**: ✅ **ESSENTIAL - Include Core Scripts Only**

**Core Scripts to Include:**
- `scripts/bootstrap.py` - Environment setup and initialization
- `scripts/llm_gateway.js` - Main LLM gateway with multi-provider support
- `scripts/llm_gateway.sh` - Bash wrapper for the gateway
- `scripts/claude_wrap.sh` - Claude wrapper with context management
- `scripts/codex_wrap.sh` - Local model wrapper
- `scripts/gemini_wrap.sh` - Gemini API wrapper
- `scripts/contracts_build.py` - Contract compilation
- `scripts/contracts_render.py` - Contract rendering
- `scripts/contracts_validate.py` - Contract validation

**Scripts to EXCLUDE:**
- `scripts/llmc_lock.py` - Template builder specific
- `scripts/build_kit.py` - Template builder specific
- `scripts/pdf_to_md.sh` - Document conversion
- `scripts/increase_capacity.sh` - Infrastructure management
- `scripts/gateway_cost_rollup.js` - Cost analysis (optional)
- `scripts/metrics_sinks/` - Metrics collection (optional)

**Context Magic**: These scripts provide the orchestration layer that routes requests between different LLM providers while maintaining context and contracts.

### 3. Configuration Files

**Status**: ✅ **ESSENTIAL - Include All**

**Core Config Files:**
- `llmc.toml` - Main configuration with embeddings, storage, and enrichment settings
- `config/deep_research_services.json` - Research service configuration
- `config/llmc_concurrency.env.example` - Concurrency configuration example
- `profiles/claude.yml` - Claude-specific profile configuration
- `profiles/codex.yml` - Local model profile configuration  
- `profiles/gemini.yml` - Gemini-specific profile configuration
- `presets/enrich_7b_ollama.yaml` - Model preset configuration
- `router/policy.json` - Routing policies

**Context Magic**: These files provide the configuration layer that makes the system flexible and adaptable to different environments and model preferences.

### 4. Documentation Files

**Status**: ✅ **ESSENTIAL - Core Documentation Only**

**Core Documentation:**
- `AGENTS.md` - Agent charter and operational guidelines
- `CONTRACTS.md` - Core operating contract and context requirements
- `DOCS/Key_Directory_Structure.md` - System architecture overview
- `DOCS/Local_Development_Tooling.md` - Development setup and tooling
- `DOCS/Claude_Orchestration_Playbook.md` - Claude-specific operational procedures
- `DOCS/ROUTING.md` - LLM routing and context management
- `DOCS/System_Specs.md` - Technical specifications
- `DOCS/TESTING_PROTOCOL.md` - Testing procedures and validation

**Documentation to EXCLUDE:**
- `DOCS/Template_Builder.md` - Template builder specific
- `DOCS/Template_Builder_TUI.md` - Template builder UI specific
- `DOCS/APPS/template-builder.md` - App-specific documentation
- `DOCS/APPS/web.md` - Web app documentation
- `DOCS/SETUP/CHATGPT_KICKOFF.md` - Setup automation
- Complex research and roadmap documents

**Context Magic**: This documentation provides the operational knowledge that makes the system understandable and maintainable.

### 5. Core Utilities and Integration Components

**Status**: ✅ **ESSENTIAL - Include Core Components**

**Core Utilities:**
- `tools/cache/` - Caching system for context management
- `tools/diagnostics/health_check.py` - System health monitoring
- `adapters/claude.tools.tmpl` - Claude tool template
- `adapters/codex.tools.tmpl` - Local model tool template
- `adapters/gemini.tools.tmpl` - Gemini tool template
- `node/contracts_loader.js` - Contract loading and management
- `examples/llmc/changeset_example.json` - Context example patterns
- `prompts/porting_agent.md` - Agent prompt templates
- `llmc_exec/` - Execution framework (core components only)

**Context Magic**: These utilities provide the supporting infrastructure for context caching, health monitoring, and tool integration.

## Components to EXCLUDE

### Template Builder Components
- `apps/template-builder/` - Complete template builder application
- `template/` - Template builder templates
- `scripts/llmc_lock.py` - Template locking mechanism
- `scripts/build_kit.py` - Build kit generation
- `DOCS/Template_Builder.md` - Template builder documentation
- `DOCS/Template_Builder_TUI.md` - Template builder UI docs
- `DOCS/APPS/template-builder.md` - Template builder app docs

### Legacy Web Application
- `apps/web/` - Legacy web interface
- `DOCS/APPS/web.md` - Web app documentation

### Complex Research and Development
- `research/` - Research and development files
- `DOCS/Roadmap.md` - Long-term planning documents
- `DOCS/Vertical_Slice_Plan.md` - Development planning
- Complex setup automation in `DOCS/SETUP/`

### Infrastructure Management
- `ops/` - Operations and deployment scripts
- `logs/` - Log files and outputs
- Temporary build artifacts and caches

## Template Structure Recommendation

```
living-template/
├── config/
│   ├── llmc.toml                 # Main configuration
│   ├── profiles/                 # Model profiles
│   ├── presets/                  # Model presets  
│   └── router/policy.json        # Routing policies
├── tools/
│   ├── rag/                      # RAG system
│   ├── cache/                    # Caching utilities
│   └── diagnostics/              # Health monitoring
├── scripts/
│   ├── bootstrap.py              # Setup and initialization
│   ├── llm_gateway.js           # Main LLM gateway
│   ├── llm_gateway.sh           # Gateway wrapper
│   ├── claude_wrap.sh           # Claude wrapper
│   ├── codex_wrap.sh            # Local model wrapper
│   ├── gemini_wrap.sh           # Gemini wrapper
│   ├── contracts_*.py           # Contract management
│   └── rag/                     # RAG scripts
├── docs/
│   ├── AGENTS.md                # Agent charter
│   ├── CONTRACTS.md             # Operating contract
│   ├── Key_Directory_Structure.md
│   ├── Local_Development_Tooling.md
│   ├── Claude_Orchestration_Playbook.md
│   ├── ROUTING.md
│   ├── System_Specs.md
│   └── TESTING_PROTOCOL.md
├── adapters/                     # LLM integration templates
├── node/                        # Contract loading system
├── examples/                    # Usage examples
├── prompts/                     # Agent prompts
└── llmc_exec/                   # Execution framework
```

## Key Context Management Magic

The core "magic" that should be preserved includes:

1. **RAG-powered context retrieval** - Local semantic search over codebases
2. **Multi-provider LLM routing** - Seamless switching between local and API models
3. **Contract-based context management** - Structured context requirements and validation
4. **Profile-driven configuration** - Adaptable settings for different models and use cases
5. **Incremental indexing** - Real-time codebase awareness and context updates
6. **Agent charter system** - Clear roles and operational guidelines for different LLM agents

## Implementation Priority

1. **Phase 1**: Core RAG system + basic configuration
2. **Phase 2**: LLM gateway and wrapper scripts  
3. **Phase 3**: Contract management and agent system
4. **Phase 4**: Documentation and examples

This extraction plan ensures the living template captures the essential context management capabilities that make LLM Commander effective for intelligent LLM orchestration while removing implementation-specific and experimental components.