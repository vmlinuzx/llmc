# Template Extraction Plan

## Overview

This document outlines the component extraction strategy for the LLMC living template system. It identifies which components from the full LLMC Commander should be included in the portable template and which should be excluded.

## Components to Include

### 1. Core LLM Orchestration Scripts
**Location**: `scripts/`
**Components**:
- `claude_wrap.sh` - Claude API orchestration
- `codex_wrap.sh` - CodeX/CodeT5 orchestration  
- `gemini_wrap.sh` - Gemini API orchestration
- `rag_refresh.sh` - RAG index management
- `tool_dispatch.sh` - Tool routing and dispatch
- `tool_health.sh` - Health monitoring
- `router.py` - LLM routing logic

**Rationale**: These are the core scripts that provide the LLM Commander "magic" - the main value proposition for deploying to other projects.

### 2. RAG System
**Location**: `tools/rag/`
**Components**: All files in the RAG system
**Rationale**: RAG (Retrieval-Augmented Generation) is a key capability that provides intelligent code indexing and context retrieval.

### 3. Configuration Management
**Location**: `config/`
**Components**:
- `default.toml` - System defaults
- `local.example.toml` - User override template
- `config.py` - Configuration loader with 3-tier precedence
- `cli.py` - Configuration management CLI

**Rationale**: The configuration system allows flexible deployment across different environments with proper defaults and override capabilities.

### 4. Provider Adapters
**Location**: `adapters/`
**Components**:
- `claude.tools.tmpl` - Claude tool templates
- `codex.tools.tmpl` - CodeX tool templates  
- `gemini.tools.tmpl` - Gemini tool templates

**Rationale**: Provider-specific configurations enable multi-provider support and easy provider switching.

### 5. Documentation
**Location**: Various locations
**Components**:
- `AGENTS.md` - Agent definitions
- `CONTRACTS.md` - Contract specifications
- `DOCS/ROUTING.md` - Routing documentation
- `DOCS/SCRIPTS/README.md` - Script documentation
- `DOCS/SETUP/CHATGPT_KICKOFF.md` - Setup guide
- `DOCS/SETUP/Editor_Hooks.md` - Editor integration
- `DOCS/SETUP/TreeSitter_Backbone.md` - Code parsing setup

**Rationale**: Documentation ensures proper setup and usage of the deployed components.

### 6. Presets and Profiles
**Location**: `presets/` and `profiles/`
**Components**:
- All preset files (e.g., `enrich_7b_ollama.yaml`)
- All profile files (e.g., `claude.yml`, `gemini.yml`)

**Rationale**: Presets and profiles provide ready-to-use configurations for common scenarios.

### 7. Caching and Diagnostics
**Location**: `tools/cache/` and `tools/diagnostics/`
**Components**:
- All cache management tools
- All diagnostic and health check tools

**Rationale**: These tools support the core RAG and LLM systems with performance optimization and monitoring.

## Components to Exclude

### 1. Template Builder Applications
**Location**: `apps/template-builder/`
**Components**: Entire application directory
**Rationale**: The template builder is a development tool for creating templates, not a component to be deployed with templates.

### 2. Web Applications
**Location**: `apps/web/`
**Components**: Entire application directory
**Rationale**: Web interfaces are not needed in deployed templates and add complexity.

### 3. Research and Documentation
**Location**: `research/` and various `DOCS/` files
**Components**:
- Research papers and documents
- Implementation logs and changelogs
- Roadmap and planning documents
- Testing protocols and playbooks

**Rationale**: Research and planning documents are useful for development but not needed in deployed templates.

### 4. Build and Development Tools
**Location**: Various locations
**Components**:
- `scripts/bootstrap.py` - Development bootstrap
- `scripts/build_kit.py` - Kit building scripts
- `scripts/template_builder_tui.sh` - Template builder TUI
- Various deployment and CI/CD scripts

**Rationale**: Development and build tools are only needed during template creation, not deployment.

### 5. Test Repositories
**Location**: `test_repo/`
**Components**: Entire test directory
**Rationale**: Test repos are for validation, not part of the template deployment.

### 6. Runtime Data
**Location**: Various locations
**Components**:
- `.rag/` - Existing RAG indexes and data
- `.llmc/` - Runtime state files
- `logs/` - Log files
- Database files and caches

**Rationale**: Runtime data is project-specific and should be generated fresh in target projects.

### 7. Productization Kits
**Location**: `llmc_productization_kit/`
**Components**: Entire productization kit directory
**Rationale**: This is legacy packaging that should be replaced by the living template system.

## Extraction Strategy

### 1. Selective Copying
Only copy the components listed in "Components to Include" with appropriate path adjustments.

### 2. Path Adjustment
When moving components from the current structure to the clean `llmc/` structure:
- Scripts: Adjust relative paths to point to new structure
- Configuration: Ensure all paths work within `llmc/` folder
- Documentation: Update any absolute paths to be relative

### 3. Configuration Generation
Create appropriate configuration files for the target structure:
- Default configuration with correct paths
- Local example configuration for user overrides
- Runtime directory structure (`.llmc/` folder)

### 4. Metadata Creation
Generate deployment metadata including:
- Source version information
- Extraction timestamp
- Component inventory
- Configuration requirements

## Implementation Steps

1. **Component Identification**: Identify all files matching inclusion criteria
2. **Path Adjustment**: Update all relative paths for new structure
3. **Configuration Creation**: Generate proper configuration files
4. **Metadata Generation**: Create deployment and tracking metadata
5. **Validation**: Ensure all components work in new structure

## Validation Criteria

After extraction, the template should be validated against:
- ✅ All included scripts run successfully
- ✅ Configuration loads properly with 3-tier precedence
- ✅ RAG system initializes correctly
- ✅ Provider adapters work with configured APIs
- ✅ Documentation is accurate and complete
- ✅ No hardcoded absolute paths remain
- ✅ Runtime directories are created correctly

This extraction plan ensures the living template contains only the essential components needed for LLM orchestration while excluding development tools and project-specific data.