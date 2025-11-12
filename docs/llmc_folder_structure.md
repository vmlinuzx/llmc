# LLMC Folder Structure Design

## Overview

This document outlines the proposed folder structure for the `llmc/` directory that will be stamped into target repositories. The design prioritizes minimal footprint, clear separation of concerns, and easy configuration management.

## Design Principles

1. **Minimal Footprint**: Only essential files that add value to target repos
2. **Separation of Concerns**: Clear distinction between template files and user-configurable files
3. **Logical Organization**: Group related components together
4. **Path Adjustability**: Files designed to be moved without breaking internal references
5. **Configuration Management**: Centralized config with project-specific overrides

## Proposed Structure

```
llmc/
├── README.md                          # Quick start guide for target repos
├── .gitignore                         # LLMC-specific ignore patterns
│
├── config/
│   ├── default.toml                   # Default configuration (template)
│   ├── local.example.toml            # Example local config to copy
│   └── profiles/                      # Model profile configurations
│       ├── claude.yml
│       ├── codex.yml
│       └── gemini.yml
│
├── scripts/                           # Executable orchestration scripts
│   ├── bootstrap.sh                   # Initial setup script
│   ├── codex_wrap.sh                  # Codex orchestration wrapper
│   ├── claude_wrap.sh                 # Claude orchestration wrapper
│   ├── gemini_wrap.sh                 # Gemini orchestration wrapper
│   ├── llm_gateway.sh                 # LLM gateway router
│   └── rag_refresh.sh                 # RAG index maintenance
│
├── tools/                             # Python utilities and libraries
│   ├── __init__.py
│   ├── rag/                          # RAG indexing and search tools
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── indexer.py
│   │   ├── search.py
│   │   └── config.py
│   ├── deep_research/                 # Deep research utilities
│   │   └── __init__.py
│   └── cache/                         # Caching utilities
│       └── __init__.py
│
├── templates/                         # Project templates (user-modifiable)
│   ├── agents/                        # Agent configuration templates
│   │   ├── claude.tools.tmpl
│   │   ├── codex.tools.tmpl
│   │   └── gemini.tools.tmpl
│   ├── contracts/                     # Contract templates
│   │   └── base.md
│   └── prompts/                       # Prompt templates
│       └── base.md
│
├── api/                               # HTTP API components
│   ├── server.py                      # FastAPI server
│   └── __init__.py
│
├── apps/                              # Optional applications (if needed)
│   └── template-builder/              # Next.js template builder
│       ├── package.json
│       ├── next.config.mjs
│       └── app/
│
├── presets/                           # Pre-configured settings
│   ├── enrich_7b_ollama.yaml
│   └── basic_local.yaml
│
├── examples/                          # Usage examples
│   ├── configs/
│   │   └── basic_setup.toml
│   └── workflows/
│       └── quick_start.sh
│
└── .llmc/                            # Runtime data (git-ignored)
    ├── index/                         # RAG index storage
    ├── cache/                         # Runtime cache
    └── logs/                          # Operation logs
```

## Key Design Decisions

### 1. Separation of Template and Config Files

**Template Files** (in `templates/`):
- User-modifiable starting points
- Named with `.tmpl` extension for clarity
- Copied to working directory on first use

**Configuration Files** (in `config/`):
- System defaults in `default.toml`
- User overrides in `local.toml` (git-ignored)
- Model profiles in `profiles/`

### 2. Path Adjustment Strategy

**Relative Path References**:
- All internal references use relative paths from `llmc/` root
- Scripts reference other files using `$(dirname "$0")/../relative/path`
- Python modules use `__file__` for path resolution

**Runtime Paths**:
- `templates/` → copied to project root on use
- `config/` → read from relative paths
- `.llmc/` → created automatically with git-ignore

### 3. Configuration Management

```toml
# config/default.toml (template - can be overridden)
[embeddings]
preset = "e5"
model = "intfloat/e5-base-v2"

[storage]
index_path = ".llmc/index/index_v2.db"

[enrichment]
enabled = false
model = "gpt-4o-mini"
batch_size = 50

# config/local.example.toml (user config - copy and modify)
[embeddings]
# Uncomment and modify as needed
# model = "custom-model-name"

[enrichment]
# Override defaults
enabled = true
model = "local-model"
```

**Precedence**:
1. Environment variables
2. `config/local.toml` (user config)
3. `config/default.toml` (system defaults)

### 4. Minimal Footprint Approach

**Always Included**:
- Core scripts in `scripts/`
- Essential tools in `tools/rag/`
- Configuration templates
- Quick start documentation

**Optional Components**:
- `apps/template-builder/` (only if template builder is needed)
- `examples/` (documentation only)
- Extended presets and profiles

**Runtime-Only** (git-ignored):
- `.llmc/` directory
- Index files
- Cache directories
- Log files

### 5. Bootstrap Process

**Initial Setup** (`scripts/bootstrap.sh`):
1. Check for required dependencies (Python, Node.js if needed)
2. Copy `config/local.example.toml` to `config/local.toml`
3. Create `.llmc/` directories with proper permissions
4. Validate configuration
5. Run initial RAG index if needed

**Zero-Config Usage**:
- Works out-of-the-box with sane defaults
- No user configuration required for basic operation
- Progressive enhancement through `config/local.toml`

## Migration Strategy for Existing Repos

When stamping this structure into existing repos:

1. **Phase 1: Core Integration**
   - Add `llmc/` directory with core components
   - Add `.gitignore` entries
   - Run bootstrap script

2. **Phase 2: Component Migration**
   - Move existing `scripts/` to `llmc/scripts/`
   - Move `tools/rag/` to `llmc/tools/rag/`
   - Update references in existing files

3. **Phase 3: Configuration Harmonization**
   - Consolidate existing configs into `config/default.toml`
   - Create example user config
   - Test all integration points

## File Path Adjustments

### Scripts
```bash
# Before: scripts/codex_wrap.sh
# After:  llmc/scripts/codex_wrap.sh

# Update internal references:
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LLMC_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_TOOLS="$LLMC_ROOT/tools"
```

### Python Imports
```python
# Before: from tools.rag import indexer
# After:  from llmc.tools.rag import indexer

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "tools"))
```

### Configuration Loading
```python
# Load config with fallback chain
def load_config():
    config_path = Path("llmc/config/local.toml")
    if not config_path.exists():
        config_path = Path("llmc/config/default.toml")
    
    with open(config_path) as f:
        return toml.load(f)
```

## Benefits of This Structure

1. **Clear Boundaries**: Easy to identify what's system vs. user code
2. **Minimal Impact**: Only adds value without cluttering the repo
3. **Flexible Configuration**: Supports both zero-config and full customization
4. **Logical Grouping**: Related functionality lives together
5. **Version Control Friendly**: User configs are git-ignored, templates are tracked
6. **Portable**: Can be easily moved or copied between repos
7. **Maintainable**: Clear separation makes updates easier

## Usage Examples

### Basic Usage (Zero Config)
```bash
# Just works with defaults
./llmc/scripts/codex_wrap.sh "generate a hello world script"
```

### Custom Configuration
```bash
# 1. Copy example config
cp llmc/config/local.example.toml llmc/config/local.toml

# 2. Edit as needed
vim llmc/config/local.toml

# 3. Use custom config
LLMC_CONFIG=llmc/config/local.toml ./llmc/scripts/codex_wrap.sh "task"
```

### Template Customization
```bash
# Copy template to project root for editing
cp llmc/templates/agents/claude.tools.tmpl ./claude.tools.yaml

# Use custom template
CLAUDE_TOOLS=./claude.tools.yaml ./llmc/scripts/claude_wrap.sh "task"
```

This structure provides a solid foundation for the LLMC system while maintaining simplicity and flexibility for different use cases.
