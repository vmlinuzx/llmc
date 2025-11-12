# LLMC Folder Structure Design

## Overview

This document defines the target folder structure for the LLMC (LLM Commander) living template system. The goal is to create a clean, portable deployment structure that can be easily deployed to other repositories without interfering with existing project files.

## Target Structure

### Clean `llmc/` Folder Design

When deployed to a target repository, the LLMC system should create a clean, self-contained `llmc/` folder with the following structure:

```
target_repo/
├── .git/                    ← Existing git repo (unchanged)
├── existing_files/          ← Existing project files (unchanged)
└── llmc/                    ← NEW clean LLMC deployment
    ├── scripts/             ← LLM orchestration scripts
    ├── config/              ← Configuration management
    ├── tools/               ← RAG, cache, diagnostics
    ├── adapters/            ← Provider-specific templates
    ├── docs/                ← Documentation
    ├── examples/            ← Example configurations
    ├── presets/             ← LLM presets and profiles
    ├── profiles/            ← Provider profiles
    ├── prompts/             ← System prompts
    └── .llmc/               ← Runtime state (gitignored)
        ├── indexes/         ← RAG indexes
        ├── cache/           ← Cache files
        ├── logs/            ← Runtime logs
        └── metadata/        ← Deployment metadata
```

## Component Details

### `scripts/` - LLM Orchestration Scripts
- `claude_wrap.sh` - Claude API wrapper
- `codex_wrap.sh` - CodeX/CodeT5 wrapper  
- `gemini_wrap.sh` - Gemini API wrapper
- `rag_refresh.sh` - RAG index refresh
- `tool_dispatch.sh` - Tool dispatcher
- `router.py` - LLM routing logic

### `config/` - Configuration Management
- `default.toml` - System defaults
- `local.toml` - Project-specific overrides
- `env_config.py` - Environment variable loader
- `cli.py` - Configuration management CLI

### `tools/` - Core Tools
- `rag/` - RAG (Retrieval-Augmented Generation) system
- `cache/` - Caching infrastructure  
- `diagnostics/` - Health checks and diagnostics

### `adapters/` - Provider Templates
- `claude.tools.tmpl` - Claude tool templates
- `codex.tools.tmpl` - CodeX tool templates
- `gemini.tools.tmpl` - Gemini tool templates

### `docs/` - Documentation
- `ROUTING.md` - LLM routing documentation
- `SCRIPTS/README.md` - Script documentation
- `SETUP/` - Setup guides

### `examples/` - Example Configurations
- `llmc/` - Example LLMC configurations
- `profiles/` - Example provider profiles

### `presets/` - LLM Presets
- `enrich_7b_ollama.yaml` - Example Ollama preset
- Additional preset files for different providers

### `profiles/` - Provider Profiles
- `claude.yml` - Claude configuration profile
- `codex.yml` - CodeX configuration profile
- `gemini.yml` - Gemini configuration profile

### `prompts/` - System Prompts
- `porting_agent.md` - Porting agent prompts
- Additional prompt templates

### `.llmc/` - Runtime State (Gitignored)
- `.gitignore` - Ensures runtime files are not committed
- `indexes/` - RAG vector indexes
- `cache/` - Generated cache files
- `logs/` - Runtime logs and metrics
- `metadata/` - Deployment and configuration metadata

## Key Principles

### 1. Clean Separation
- LLMC components are isolated in the `llmc/` folder
- No interference with existing project files
- Self-contained system that can be removed if needed

### 2. Portable Configuration
- 3-tier configuration hierarchy:
  - Default (system-wide)
  - Local (project-specific)
  - Environment (runtime overrides)
- All paths are relative to the `llmc/` folder

### 3. Maintainable Structure
- Clear separation of concerns
- Consistent naming conventions
- Documentation integrated into structure

### 4. Runtime Isolation
- `.llmc/` folder contains all runtime state
- Gitignored to prevent accidental commits
- Can be regenerated if deleted

### 5. Provider Flexibility
- Multiple LLM provider support
- Easy to add new providers
- Configuration-driven provider selection

## Migration Path

### From Current Structure
The current LLMC Commander structure includes many additional components (template builder, web apps, research docs) that should NOT be included in the template deployment. The living template system extracts only the portable components.

### To Clean Structure
The extractor transforms the current structure into the clean target structure by:
1. Selecting relevant components
2. Adjusting relative paths
3. Creating appropriate configuration
4. Generating deployment metadata

## Validation

The structure should be validated against these criteria:
- ✅ Can be deployed to any repository without conflicts
- ✅ All paths are relative and portable
- ✅ Configuration is flexible and overrideable
- ✅ Runtime state is properly isolated
- ✅ Documentation is complete and accessible
- ✅ All LLM orchestration scripts are functional
- ✅ RAG system works independently
- ✅ Provider configurations are maintained

## Benefits

1. **Clean Deployment**: Target repos get organized `llmc/` folder
2. **Manual Control**: Updates are manual when LLM Commander improves
3. **Preservation**: Original LLM Commander stays untouched
4. **Flexibility**: 3-tier configuration for any environment
5. **Safety**: Easy rollback and validation

This structure solves the "dog eating its own food" problem by providing a clean, maintainable way to share LLM Commander's capabilities across multiple projects.