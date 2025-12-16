# Enrichment Config TUI

**Interactive visual editor for managing enrichment chains in `llmc.toml`**

## Quick Start

```bash
# Launch the TUI
llmc config
```

## Features

### ✅ Phase 1 - Read-Only Viewer (MVP - Implemented)

- **Visual Hierarchy Display** - See routing → chain → tier structure at a glance
- **Route Mapping** - Understand which content types route to which chains
- **Cascade Visualization** - View tier-based fallback ordering
- **Live Validation** - Check config integrity without daemon restarts
- **Config Reload** - Refresh view from disk

### 🚧 Phase 2 - Safe Editing (Coming Soon)

- **Duplicate Chains** - Copy existing chains as templates
- **Edit Chain Properties** - Modify provider, model, tier, etc.
- **Validation on Save** - Prevent broken configs
- **Automatic Backups** - Timestamped backups before every save

### 🎯 Phase 3 - Advanced Operations (Planned)

- **Delete Chains** - With safety checks and warnings
- **Routing Simulator** - Test file paths → chain routing
- **Name Suggestions** - Follow consistent naming conventions
- **Test Connections** - Verify provider URLs
- **Undo/Redo** - Rollback changes

## Current Capabilities

### Visual Hierarchy

The TUI displays your enrichment configuration as a collapsible tree:

```
📋 Routed Chains
├─ docs → minimax_docs
│  ├─ ✓ minimax-docs (7b, minimax, primary)
│  ├─ ✓ minimax-fallback-7b (7b, ollama, fallback)
│  └─ ✓ minimax-fallback-14b (14b, ollama, fallback)
│
└─ code → athena
   ├─ ✓ athena (7b, ollama, primary)
   └─ ✓ athena-14b (14b, ollama, fallback)

⚠️  Unrouted Chains
├─ google (disabled)
└─ groq-70b (disabled)

ℹ️  Configuration Info
├─ Default Chain: athena
├─ Routing Enabled: True
├─ Total Chains: 7
└─ Total Routes: 2
```

### Validation

Checks for common errors:
- ✓ Duplicate chain names
- ✓ Missing required fields (name, provider, model, tier)
- ✓ Invalid routing tiers
- ✓ Broken route references
- ✓ Invalid provider names

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `v` | Validate config |
| `r` | Reload from disk |
| `s` | Simulate routing (Phase 3) |
| `?` | Help (Phase 3) |

## Architecture

### Design Philosophy

**TUI as Editor, TOML as Source of Truth**

- ✅ `llmc.toml` remains the single source of truth
- ✅ Git-friendly: track changes, diff configs, rollback
- ✅ Portable: no separate database
- ✅ Service-friendly: daemon reads TOML directly

### Workflow: Duplicate → Modify → Delete

Instead of complex rename tracking, we use a template-based workflow:

1. **Duplicate** an existing chain as a starting point
2. **Modify** the copy (change name, model, tier, etc.)
3. **Delete** the old chain (with safety checks)

This avoids cascading reference updates and makes operations atomic.

## Example Use Cases

### Adding a New Model Tier

**Before TUI:**
```toml
# Manually copy-paste and modify 20+ lines of TOML
# Risk: syntax errors, duplicate names, broken references
```

**With TUI:**
1. Navigate to existing chain (e.g., `athena`)
2. Press `d` to duplicate
3. Edit name: `athena` → `athena-3b`
4. Edit model: `qwen2.5:7b` → `qwen2.5:3b`
5. Edit tier: `7b` → `3b`
6. Save → TUI validates and writes TOML

### Cleaning Up Dead Chains

**Before TUI:**
```toml
# Hard to know which chains are actually used
# Risk: delete wrong chain, break routing
```

**With TUI:**
1. View hierarchy → see "⚠️ Unrouted Chains" section
2. Select orphaned chain (e.g., `groq-70b`)
3. Press `Del` → TUI checks: "0 references, safe to delete"
4. Confirm → chain removed from TOML

### Understanding Routing Flow

**Before TUI:**
```toml
# Need to mentally map: file ext → slice_type → route → chain → backends
# Confusing with 10+ chains and multiple routes
```

**With TUI:**
1. Press `s` for simulator (Phase 3)
2. Enter file path: `src/llmc/tools/rag/pipeline.py`
3. See full routing decision:
   - Extension: `.py`
   - Slice Type: `code`
   - Route: `code → athena`
   - Cascade: `athena (7b)` → `athena-14b (14b)`

## Naming Conventions

### Recommended Patterns

**Chain names:** `{provider}-{purpose}[-{tier}]`
```toml
ollama-code-7b       # Ollama, code enrichment, 7B tier
minimax-docs         # Minimax, docs enrichment, primary
minimax-docs-7b      # Minimax, docs enrichment, 7B fallback
anthropic-premium    # Anthropic, premium tier
```

**Chain groups:** `{purpose}[_{provider}]`
```toml
code           # Default code chain
docs_minimax   # Docs chain using Minimax
premium        # Premium quality chain
```

The TUI will help enforce these conventions in Phase 3.

## Development Status

| Feature | Status | Phase |
|---------|--------|-------|
| Visual hierarchy display | ✅ Done | MVP |
| Route mapping view | ✅ Done | MVP |
| Config validation | ✅ Done | MVP |
| Reload from disk | ✅ Done | MVP |
| Duplicate chains | 🚧 Next | Phase 2 |
| Edit chain properties | 🚧 Next | Phase 2 |
| Save with backup | 🚧 Next | Phase 2 |
| Delete chains | 📋 Planned | Phase 3 |
| Routing simulator | 📋 Planned | Phase 3 |
| Name suggestions | 📋 Planned | Phase 3 |
| Test connections | 📋 Planned | Phase 3 |
| Undo/redo | 📋 Planned | Phase 3 |

## Technical Details

### Dependencies

- **Textual** (≥0.41.0) - Modern Python TUI framework
- **tomllib** (Python 3.11+, stdlib) or **tomli** (backport)
- **tomli-w** or **tomlkit** - TOML writing

Already in `pyproject.toml`:
```toml
dependencies = [
  "textual>=0.41.0",
  "tomli-w>=1.0.0",
  "tomlkit>=0.12.0"
]
```

### File Structure

```
llmc/
├── config/
│   ├── __init__.py        # Public API
│   ├── manager.py         # ConfigManager (load/save/validate)
│   ├── operations.py      # ChainOperations (duplicate/delete)
│   ├── simulator.py       # RoutingSimulator
│   └── tui.py             # Textual app
└── commands/
    └── config.py          # CLI entry point
```

### Core Classes

- **ConfigManager** - TOML read/write with backup
- **ChainOperations** - High-level CRUD operations
- **RoutingSimulator** - Test routing decisions
- **ConfigTUI** - Main Textual application

## Troubleshooting

### "Missing required dependency for TUI"

Install textual:
```bash
pip install textual
```

Or install the full TUI extras:
```bash
pip install -e ".[tui]"
```

### "Could not find llmc.toml"

Run from repo root or specify path:
```bash
llmc config --config-path /path/to/llmc.toml
```

### Changes not reflected in daemon

After editing config, restart the RAG daemon:
```bash
llmc service restart
```

### Want to revert changes

Backups are created automatically:
```bash
ls llmc.toml.bak.*
# Restore from backup
cp llmc.toml.bak.20251204_154000 llmc.toml
```

## Roadmap

See [`DOCS/planning/config_tui_sdd.md`](../planning/config_tui_sdd.md) for full design document.

### Phase 2 - Safe Editing (Next Sprint)
- Duplicate chain UI
- Edit chain form with validation
- Save with automatic backup
- Improved error messages

### Phase 3 - Advanced Operations (Future)
- Delete chain with safety checks
- Routing simulator
- Name suggestion helper
- Connection testing
- Undo/redo stack

### Phase 4 - Polish (Future)
- Dark/light themes
- Help system with `?`
- Performance optimization
- Import/export chain templates

## Contributing

When adding features to the TUI:

1. **Update the SDD** first (`DOCS/planning/config_tui_sdd.md`)
2. **Add validation logic** to `ConfigManager.validate()`
3. **Add operations** to `ChainOperations` if needed
4. **Create Textual screens** in `tui.py`
5. **Update this README** with new capabilities
6. **Add tests** (textual supports pilot testing)

---

**Status:** MVP Complete (Phase 1)  
**Next Milestone:** Phase 2 - Safe Editing  
**See Also:** [Config TUI SDD](../planning/config_tui_sdd.md)
