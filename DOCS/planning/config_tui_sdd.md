# Enrichment Config TUI - Software Design Document

## Overview
An interactive Text User Interface (TUI) for managing the complex enrichment configuration hierarchy in `llmc.toml`. Provides visual editing, validation, and safe operations for chain management without the pain of manual TOML editing.

## Problem Statement

### Current Pain Points
1. **Complex Hierarchy** - Multi-level routing (`slice_type → route → chain → tiers`) is hard to visualize in flat TOML
2. **Naming Inconsistency** - Chains have inconsistent naming (e.g., `minimax-docs` vs `minimax_docs` vs `minimax-fallback-7b`)
3. **Easy to Break** - TOML syntax errors, duplicate chains, broken references
4. **Cascading Changes** - Renaming a chain requires updating multiple sections (`[[enrichment.chain]]`, `[enrichment.routes]`, etc.)
5. **No Validation** - Easy to create invalid configs (wrong tiers, missing URLs, etc.)
6. **Difficult to Understand Flow** - Hard to trace: "What happens when I enrich a .md file?"

### User Workflow Frustrations
- "I want to add a new model but I need to copy-paste and modify 20 lines of TOML"
- "I renamed a chain but forgot to update the route mapping"
- "I have 3 chains in the 'athena' cascade, are they in the right order?"
- "Which tier should my new model be in?"

## Goals

### Primary Goals
1. **Visual Hierarchy** - See the entire routing → chain → tier structure at a glance
2. **Template Operations** - Duplicate chains and modify copies (avoid rename complexity)
3. **Safe Deletion** - Warn when deleting chains that are referenced elsewhere
4. **Live Validation** - Catch errors before they hit the daemon
5. **Single Source of Truth** - Edit `llmc.toml` directly, no separate config database

### Non-Goals
- ❌ Replace `llmc.toml` with a database
- ❌ Support editing non-enrichment config sections (embeddings, MCP, etc.) in v1
- ❌ Runtime config hot-reload (daemon still needs restart)
- ❌ Multi-user concurrent editing

## Architecture

### Design Principles
1. **TUI as Editor, TOML as Source** - TUI reads/writes `llmc.toml` directly
2. **Template-Based Workflow** - Duplicate → Modify → Delete (no rename tracking)
3. **Fail-Safe Operations** - Validate before write, backup on changes
4. **Progressive Disclosure** - Show overview by default, drill down for details

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    llmc config tui                          │
│  (Interactive TUI - Textual Framework)                      │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─► Display Layer (Textual Widgets)
             │   ├─ Hierarchy Tree View
             │   ├─ Chain Editor Form
             │   ├─ Routing Simulator
             │   └─ Validation Alerts
             │
             ├─► Business Logic
             │   ├─ ConfigManager (load/save TOML)
             │   ├─ ChainOperations (duplicate/delete)
             │   ├─ Validator (check config integrity)
             │   └─ RoutingTracer (simulate file → chain flow)
             │
             └─► Data Model
                 ├─ EnrichmentConfig (Pydantic model)
                 ├─ ChainDefinition
                 ├─ RouteMapping
                 └─ TierMetadata
```

### Data Flow

```
User Action
    ↓
TUI Event Handler
    ↓
Business Logic Operation
    ↓
Validate Changes
    ↓
Backup llmc.toml → llmc.toml.bak
    ↓
Write to llmc.toml
    ↓
Reload Display
```

## Feature Specification

### 1. Hierarchy Visualizer

**View: Main Dashboard**

```
┌─ Enrichment Configuration ─────────────────────────────────────┐
│                                                                 │
│ Routing Overview                                               │
│ ┌─ Route: docs → minimax_docs                                 │
│ │  Chains: minimax-docs (7b) → minimax-fallback-7b (7b)       │
│ │         → minimax-fallback-14b (14b)                         │
│ │  Status: ✓ 3 backends, valid cascade                        │
│ │                                                              │
│ └─ Route: code → athena                                        │
│    Chains: athena (7b) → athena-14b (14b)                     │
│    Status: ✓ 2 backends, valid cascade                        │
│                                                                 │
│ Unrouted Chains                                                │
│ ├─ google [disabled] - 0 references                           │
│ └─ groq-70b [disabled] - 0 references                          │
│                                                                 │
│ [A]dd Chain  [E]dit  [D]uplicate  [Del]ete  [S]imulate  [Q]uit│
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Collapsible tree view of routing hierarchy
- Color coding: green (active), yellow (disabled), red (errors)
- Show chain count, tier order, reference count
- Highlight orphaned chains (not referenced anywhere)

### 2. Chain Editor

**View: Edit/Create Chain**

```
┌─ Edit Chain: minimax-docs ─────────────────────────────────────┐
│                                                                 │
│ Name: [minimax-docs___________________]  (internal identifier) │
│ Chain: [minimax_docs__________________]  (cascade group name)  │
│ Provider: [minimax ▼]                                          │
│ Model: [MiniMax-M2____________________]                        │
│ URL: [https://api.minimax.io/anthropic/v1]                     │
│ Routing Tier: [7b ▼]  (3b, 7b, 14b, 70b)                      │
│ Timeout: [60______] seconds                                     │
│ Enabled: [✓]                                                    │
│                                                                 │
│ Options (TOML dict):                                           │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ # num_ctx = 8192                                            ││
│ │ # temperature = 0.2                                         ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ References: Used by routes → docs                              │
│                                                                 │
│ [S]ave  [C]ancel  [T]est Connection                           │
└─────────────────────────────────────────────────────────────────┘
```

**Validation (on save):**
- ✓ Name is unique
- ✓ Chain name exists
- ✓ Provider is in allowed list
- ✓ URL is valid HTTP/HTTPS
- ✓ Tier is in allowed list (3b, 7b, 14b, 70b)
- ⚠️ Warn if chain not referenced anywhere

### 3. Duplicate Chain (Template Workflow)

**User Flow:**
1. Select chain to duplicate: `athena`
2. TUI shows: "Create new chain based on 'athena'"
3. Pre-fill form with copied values
4. User edits name: `athena` → `athena-3b`
5. User edits model: `qwen2.5:7b` → `qwen2.5:3b`
6. User edits tier: `7b` → `3b`
7. Save → adds new `[[enrichment.chain]]` entry

**No complex rename tracking needed!**

### 4. Delete Chain

**User Flow:**
1. Select chain to delete: `athena-8b` (commented out)
2. TUI checks references:
   - ✓ Not used in any routes
   - ✓ Chain `athena` has other members (athena, athena-14b)
3. Show confirmation:
   ```
   Delete chain 'athena-8b'?
   
   ⚠️  This chain is currently disabled.
   ✓  No active routes reference this chain.
   ✓  Chain 'athena' will still have 2 active backends.
   
   [Y]es, delete  [N]o, cancel
   ```
4. On confirm → remove from TOML

**Safe Deletion Checks:**
- ❌ Block if it's the only backend in an active route
- ⚠️ Warn if it's referenced in routes but has siblings
- ✓ Allow if orphaned (no references)

### 5. Routing Simulator

**View: Test Routing Logic**

```
┌─ Routing Simulator ────────────────────────────────────────────┐
│                                                                 │
│ Input File Path: [src/llmc/tools/rag/pipeline.py___________]  │
│                                                                 │
│ Simulation Result:                                             │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ File: src/llmc/tools/rag/pipeline.py                        ││
│ │ Extension: .py                                              ││
│ │ Slice Type: code                                            ││
│ │                                                              ││
│ │ Route: code → athena                                        ││
│ │                                                              ││
│ │ Cascade Order:                                              ││
│ │   1. athena (7b tier)                                       ││
│ │      Provider: ollama                                       ││
│ │      Model: qwen2.5:7b-instruct                             ││
│ │      URL: http://192.168.5.20:11434                         ││
│ │                                                              ││
│ │   2. athena-14b (14b tier) [fallback]                       ││
│ │      Provider: ollama                                       ││
│ │      Model: qwen2.5:14b-instruct-q4_K_M                     ││
│ │      URL: http://192.168.5.20:11434                         ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ [T]est Another  [B]ack                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Test Cases:**
- `docs/planning/foo.md` → should route to minimax_docs
- `src/llmc/core.py` → should route to athena
- `tests/test_pipeline.py` → should route to default

### 6. Naming Convention Helper

**Suggested Conventions:**

```toml
# Chain naming pattern: {provider}-{purpose}[-{tier}]
# Examples:
#   ollama-code-7b      (Ollama, code enrichment, 7B tier)
#   minimax-docs        (Minimax, docs enrichment, primary)
#   minimax-docs-7b     (Minimax, docs enrichment, 7B fallback)
#   anthropic-premium   (Anthropic, premium tier)

# Chain group naming pattern: {purpose}[_{provider}]
# Examples:
#   code           (default code chain)
#   docs_minimax   (docs chain using Minimax)
#   premium        (premium quality chain)
```

**TUI Feature: Name Validator**
- Suggest names based on provider + tier
- Highlight non-standard names
- Offer "quick rename" via duplicate-modify-delete

## Technical Implementation

### Tech Stack
- **Framework**: [Textual](https://github.com/Textualize/textual) - Modern Python TUI
- **Config Parsing**: `toml` or `tomli/tomli-w` (stdlib in Python 3.11+)
- **Validation**: Pydantic models (reuse existing enrichment config models)
- **Testing**: pytest + Textual pilot (TUI testing)

### File Structure

```
llmc/
├── commands/
│   └── config.py          # CLI entry point: `llmc config`
├── config/
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py         # Main Textual app
│   │   ├── screens/
│   │   │   ├── dashboard.py       # Hierarchy overview
│   │   │   ├── chain_editor.py    # Edit/create chain
│   │   │   ├── simulator.py       # Routing simulator
│   │   │   └── validator.py       # Config validation view
│   │   ├── widgets/
│   │   │   ├── chain_tree.py      # Tree view widget
│   │   │   ├── chain_form.py      # Form widget
│   │   │   └── status_bar.py      # Status/help bar
│   │   └── models.py      # Pydantic models
│   └── manager.py         # ConfigManager (load/save/validate)
└── tools/rag/
    └── config_enrichment.py  # Existing validation (reuse)
```

### Core Classes

```python
# llmc/config/manager.py
class ConfigManager:
    """Manages llmc.toml read/write/backup operations."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config: dict = {}
    
    def load(self) -> dict:
        """Load and parse llmc.toml."""
        
    def save(self, config: dict) -> None:
        """Backup current config and write new one."""
        
    def backup(self) -> Path:
        """Create timestamped backup."""
        
    def validate(self, config: dict) -> list[str]:
        """Return list of validation errors."""

# llmc/config/tui/operations.py
class ChainOperations:
    """High-level chain CRUD operations."""
    
    def duplicate_chain(self, chain_name: str) -> dict:
        """Create a copy of a chain definition."""
        
    def delete_chain(self, chain_name: str) -> tuple[bool, list[str]]:
        """Delete chain, return (can_delete, warnings)."""
        
    def get_chain_references(self, chain_name: str) -> list[str]:
        """Find all routes referencing this chain."""
        
    def get_cascade_order(self, chain_group: str) -> list[dict]:
        """Get all chains in a cascade, sorted by tier."""

# llmc/config/tui/simulator.py
class RoutingSimulator:
    """Simulate routing decisions for test inputs."""
    
    def simulate_file(self, file_path: str) -> dict:
        """Return routing decision for a file path."""
        # Returns: {slice_type, route, chain, backends: [...]}
```

## UI/UX Design

### Color Scheme
- **Green** - Active, healthy chains
- **Yellow** - Disabled chains, warnings
- **Red** - Errors, invalid configs
- **Blue** - Highlighted/selected items
- **Gray** - Comments, metadata

### Keyboard Shortcuts
- `j/k` or `↑/↓` - Navigate
- `Enter` - Select/Edit
- `d` - Duplicate chain
- `Del` - Delete chain
- `s` - Open simulator
- `v` - Validate config
- `r` - Refresh from disk
- `q` - Quit
- `?` - Help

### Help System
- `?` shows contextual help overlay
- Status bar shows available commands
- Tooltips on form fields

## Validation Rules

### Chain Validation
1. **Name uniqueness** - No duplicate chain names
2. **Provider allowed** - Must be in `_ALLOWED_PROVIDERS`
3. **Tier validity** - Must be in `_ALLOWED_TIERS`
4. **URL format** - Valid HTTP/HTTPS URL
5. **Chain group exists** - Referenced chains must exist
6. **Circular dependencies** - No chain can reference itself

### Route Validation
1. **Route target exists** - `[enrichment.routes]` must point to existing chains
2. **Slice type coverage** - Ideally all slice types have routes

### Cascade Validation
1. **Tier ordering** - Tiers should ascend (3b → 7b → 14b → 70b)
2. **Provider consistency** - Warn if mixing providers in same cascade
3. **Fallback coverage** - Warn if chain has no fallbacks

## Success Criteria

### MVP (Milestone 1)
- ✓ Display enrichment hierarchy tree
- ✓ Edit existing chains (name, model, tier, etc.)
- ✓ Duplicate chains
- ✓ Delete chains with safety checks
- ✓ Save changes to llmc.toml with backup
- ✓ Basic validation (uniqueness, required fields)

### Enhanced (Milestone 2)
- ✓ Routing simulator
- ✓ Advanced validation (tier order, references)
- ✓ Name suggestion helper
- ✓ Test connection to provider URLs
- ✓ Import/export chain templates
- ✓ Undo last change

### Future Enhancements
- Multi-repo config management
- Cloud provider auto-discovery
- Cost estimation per chain
- Performance metrics integration
- Dark/light theme toggle

## Testing Strategy

### Unit Tests
- ConfigManager load/save/validate
- ChainOperations duplicate/delete logic
- RoutingSimulator decision logic

### Integration Tests
- Full workflow: load → edit → save → verify TOML
- Validation catches real errors from user configs

### TUI Tests
- Textual provides `pilot` for automated UI testing
- Test navigation, form submission, error display

### Manual Test Cases
1. Duplicate `athena` → `athena-3b` → verify TOML
2. Delete orphaned chain → verify removed from TOML
3. Edit chain name → verify routes still reference it (via duplicate-delete workflow)
4. Simulate `src/foo.py` → verify routes to `code` → `athena`
5. Trigger validation error → verify displayed in UI

## Migration Path

### Phase 1: Read-Only Viewer (Week 1)
- Display hierarchy
- Show chain details
- Routing simulator
- **User benefit**: Understand current config

### Phase 2: Safe Editing (Week 2)
- Duplicate chains
- Edit chain properties
- Validation on save
- **User benefit**: Make changes without fear

### Phase 3: Advanced Operations (Week 3)
- Delete chains
- Name suggestion
- Test connections
- Undo/redo
- **User benefit**: Full config management

### Phase 4: Polish (Week 4)
- Improved visuals
- Help system
- Error messages
- Performance optimization
- **User benefit**: Production-ready tool

## Rollout Plan

1. **Alpha** - Internal testing with current config
2. **Beta** - Document naming conventions, test with teammates
3. **v1.0** - Ship with `llmc config` command
4. **Post-v1.0** - Collect feedback, iterate

## Open Questions

1. **Should we auto-restart daemon after config save?**
   - Pro: Immediate effect
   - Con: Might interrupt ongoing enrichment
   - **Decision**: Prompt user, don't auto-restart

2. **Should we support editing other config sections (embeddings, MCP)?**
   - **Decision**: Not in v1, add later if needed

3. **Should we validate by actually calling provider APIs?**
   - **Decision**: Optional "Test Connection" feature, not mandatory

4. **How to handle manual edits to llmc.toml while TUI is open?**
   - **Decision**: Detect file changes, prompt to reload

## References

- Textual Documentation: https://textual.textualize.io/
- Current enrichment config: `/home/vmlinux/src/llmc/llmc.toml`
- Enrichment validation: `tools/rag/config_enrichment.py`
- Related: Conversation history on routing tier errors

---

**Author**: Antigravity  
**Date**: 2025-12-04  
**Status**: Draft → Ready for Implementation
