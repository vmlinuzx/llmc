# TUI/CLI Parity - Software Design Document

## Overview

Rebuild the LLMC TUI as a **visual frontend to the CLI**. Every CLI command gets a corresponding TUI screen. Same underlying logic, different interface. When you change the CLI, you know exactly what TUI screen needs updating.

## Design Philosophy

```
┌─────────────────────────────────────────────────────────┐
│                     USER                                │
│                      │                                  │
│         ┌────────────┴────────────┐                     │
│         ▼                         ▼                     │
│    ┌─────────┐              ┌─────────┐                 │
│    │   CLI   │              │   TUI   │                 │
│    │ (typer) │              │(textual)│                 │
│    └────┬────┘              └────┬────┘                 │
│         │                        │                      │
│         └──────────┬─────────────┘                      │
│                    ▼                                    │
│            ┌──────────────┐                             │
│            │ Core Logic   │                             │
│            │ (services)   │                             │
│            └──────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

**Rules:**
1. CLI commands call service functions
2. TUI screens call the SAME service functions  
3. TUI never duplicates CLI logic
4. Adding a CLI command = adding a TUI screen

## CLI → TUI Mapping

### Main Navigation (F-keys or number keys)

| Key | CLI Command Group | TUI Screen | Description |
|-----|------------------|------------|-------------|
| `1` | `llmc` (root) | **Dashboard** | System overview, quick stats |
| `2` | `llmc search` | **Search** | Code search with results |
| `3` | `llmc service` | **Service** | Start/stop/status/logs |
| `4` | `llmc nav` | **Navigate** | Where-used, lineage |
| `5` | `llmc docs` | **Docs** | Generate docs, status |
| `6` | `llmc usertest` | **RUTA** | User testing scenarios |
| `7` | - | **Analytics** | Query stats, usage (legacy) |
| `8` | - | **Config** | Edit llmc.toml enrichment |

### Dashboard Screen (Home)

Maps to: Root-level commands + stats

```
┌─ LLMC Cyberpunk Console v0.5.5 ──────────────────────────┐
│                                                          │
│  ┌─ System Status ─────────┐  ┌─ Quick Actions ────────┐ │
│  │ Daemon: [●] ONLINE      │  │ [i] Index Repo         │ │
│  │ Files:  1,234           │  │ [s] Sync Changes       │ │
│  │ Spans:  45,678          │  │ [e] Run Enrichment     │ │
│  │ Enriched: 42,100 (92%)  │  │ [d] Run Doctor         │ │
│  │ Uptime: 4h 23m          │  │ [b] Benchmark          │ │
│  └─────────────────────────┘  └────────────────────────┘ │
│                                                          │
│  ┌─ Enrichment Log ─────────────────────────────────────┐│
│  │ 14:23:01 [INF] Processing tools/rag/service.py...    ││
│  │ 14:23:04 [OK ] Enriched 3 spans (athena-7b)          ││
│  │ 14:23:05 [INF] Processing docs/README.md...          ││
│  │ 14:23:08 [OK ] Enriched 2 spans (minimax-docs)       ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [1]Dashboard [2]Search [3]Service [4]Nav [5]Docs [q]Quit│
└──────────────────────────────────────────────────────────┘
```

**CLI mappings:**
- Stats panel → `llmc stats`
- [i] Index → `llmc index`
- [s] Sync → `llmc sync`
- [e] Enrich → `llmc enrich`
- [d] Doctor → `llmc doctor`
- [b] Benchmark → `llmc benchmark`

### Search Screen

Maps to: `llmc search <query>`

```
┌─ Search ─────────────────────────────────────────────────┐
│                                                          │
│  Query: [enrichment pipeline________________________]    │
│                                                          │
│  ┌─ Results (12 matches) ───────────────────────────────┐│
│  │ ▸ tools/rag/enrichment_pipeline.py:45               ││
│  │   class EnrichmentPipeline:                         ││
│  │   "Orchestrates the enrichment of code spans..."    ││
│  │                                                      ││
│  │ ▸ tools/rag/enrichment_router.py:23                 ││
│  │   def route_to_chain(slice_type, config):           ││
│  │   "Routes content to appropriate enrichment..."     ││
│  │                                                      ││
│  │ ▸ llmc.toml:133                                     ││
│  │   [enrichment]                                      ││
│  │   "Main enrichment configuration section..."        ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [Enter] Open  [Tab] Inspect  [/] New Search  [Esc] Back │
└──────────────────────────────────────────────────────────┘
```

**CLI mapping:**
- Search → `llmc search "enrichment pipeline"`
- Shows same results as CLI, formatted for TUI

### Service Screen

Maps to: `llmc service <subcommand>`

```
┌─ Service Management ─────────────────────────────────────┐
│                                                          │
│  ┌─ Status ────────────────┐  ┌─ Repositories ─────────┐ │
│  │ RAG Daemon: [●] RUNNING │  │ ▸ /home/vmlinux/llmc   │ │
│  │ PID: 12345              │  │   Status: Active       │ │
│  │ Memory: 234 MB          │  │   Spans: 45,678        │ │
│  │ CPU: 2.3%               │  │                        │ │
│  │                         │  │ ▸ /home/vmlinux/other  │ │
│  │ [s] Start  [x] Stop     │  │   Status: Idle         │ │
│  │ [r] Restart             │  │   Spans: 12,345        │ │
│  └─────────────────────────┘  └────────────────────────┘ │
│                                                          │
│  ┌─ Live Logs ──────────────────────────────────────────┐│
│  │ 14:23:01 [daemon] Processing batch 42/100...         ││
│  │ 14:23:04 [enrich] athena-7b responded in 1.2s        ││
│  │ 14:23:05 [embed ] Generated 128 embeddings           ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [+] Add Repo  [-] Remove Repo  [l] Toggle Logs  [Esc]   │
└──────────────────────────────────────────────────────────┘
```

**CLI mappings:**
- Status → `llmc service status`
- Start/Stop/Restart → `llmc service start/stop/restart`
- Logs → `llmc service logs -f`
- Add Repo → `llmc service repo add <path>`
- Remove Repo → `llmc service repo remove <name>`
- List Repos → `llmc service repo list`

### Navigate Screen

Maps to: `llmc nav <subcommand>`

```
┌─ Code Navigation ────────────────────────────────────────┐
│                                                          │
│  Mode: [Where Used ▼]  Entity: [EnrichmentPipeline____]  │
│                                                          │
│  ┌─ References (8 found) ───────────────────────────────┐│
│  │                                                      ││
│  │ ▸ tools/rag/service.py:234                          ││
│  │   pipeline = EnrichmentPipeline(config)             ││
│  │   └─ Instantiation in process_repo()                ││
│  │                                                      ││
│  │ ▸ tools/rag/service.py:245                          ││
│  │   pipeline.run()                                    ││
│  │   └─ Method call                                    ││
│  │                                                      ││
│  │ ▸ tests/test_enrichment.py:45                       ││
│  │   mock_pipeline = Mock(spec=EnrichmentPipeline)     ││
│  │   └─ Test mock                                      ││
│  │                                                      ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [w] Where-Used  [l] Lineage  [s] Search  [Enter] Open   │
└──────────────────────────────────────────────────────────┘
```

**CLI mappings:**
- Where Used → `llmc nav where-used EnrichmentPipeline`
- Lineage → `llmc nav lineage EnrichmentPipeline`
- Search → `llmc nav search <query>`

### Docs Screen

Maps to: `llmc docs <subcommand>`

```
┌─ Documentation Generation ───────────────────────────────┐
│                                                          │
│  ┌─ Status ────────────────┐  ┌─ Recent Activity ──────┐ │
│  │ Backend: shell          │  │ ▸ core.py - Generated  │ │
│  │ Output: DOCS/REPODOCS/  │  │ ▸ utils.py - Generated │ │
│  │ Enabled: Yes            │  │ ▸ config.py - Pending  │ │
│  │                         │  │ ▸ tui.py - Pending     │ │
│  │ Files Documented: 45    │  │                        │ │
│  │ Files Pending: 23       │  │                        │ │
│  │ Files Skipped: 12       │  │                        │ │
│  └─────────────────────────┘  └────────────────────────┘ │
│                                                          │
│  ┌─ Generation Log ─────────────────────────────────────┐│
│  │ 14:20:01 Generating docs for llmc/core.py...         ││
│  │ 14:20:03 Written: DOCS/REPODOCS/llmc/core.md         ││
│  │ 14:20:04 Generating docs for llmc/utils.py...        ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [g] Generate All  [f] Generate File  [Esc] Back         │
└──────────────────────────────────────────────────────────┘
```

**CLI mappings:**
- Status → `llmc debug autodoc status`
- Generate → `llmc debug autodoc generate [--file PATH]`

### Config Screen (Enrichment Editor)

Maps to: `llmc config` (the new enrichment config TUI I just built)

```
┌─ Enrichment Configuration ───────────────────────────────┐
│                                                          │
│  ┌─ Routing Hierarchy ──────────────────────────────────┐│
│  │ 📋 Routed Chains                                     ││
│  │ ├─ docs → minimax_docs                               ││
│  │ │  ├─ ✓ minimax-docs (7b, minimax, primary)         ││
│  │ │  ├─ ✓ minimax-fallback-7b (7b, ollama)            ││
│  │ │  └─ ✓ minimax-fallback-14b (14b, ollama)          ││
│  │ │                                                    ││
│  │ └─ code → athena                                     ││
│  │    ├─ ✓ athena (7b, ollama, primary)                ││
│  │    └─ ✓ athena-14b (14b, ollama)                    ││
│  │                                                      ││
│  │ ⚠️  Unrouted Chains                                  ││
│  │ └─ groq-70b [disabled]                              ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [d] Duplicate  [e] Edit  [Del] Delete  [t] Test Route   │
└──────────────────────────────────────────────────────────┘
```

### Analytics Screen (Legacy/Bonus)

Not in CLI - TUI-only analytics dashboard

```
┌─ Analytics Dashboard ────────────────────────────────────┐
│                                                          │
│  ┌─ Query Stats (7 days) ──┐  ┌─ Top Files ────────────┐ │
│  │ Total Queries: 1,234    │  │ 1. service.py (89)     │ │
│  │ Unique Queries: 456     │  │ 2. pipeline.py (67)    │ │
│  │ Avg Results: 4.2        │  │ 3. config.py (45)      │ │
│  │ Cache Hit Rate: 78%     │  │ 4. utils.py (34)       │ │
│  └─────────────────────────┘  └────────────────────────┘ │
│                                                          │
│  ┌─ Top Queries ────────────────────────────────────────┐│
│  │ 1. "enrichment pipeline" (23 times)                  ││
│  │ 2. "config loader" (19 times)                        ││
│  │ 3. "mcp server" (15 times)                           ││
│  │ 4. "embedding provider" (12 times)                   ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [r] Refresh  [c] Clear Stats  [Esc] Back                │
└──────────────────────────────────────────────────────────┘
```

## Architecture

### File Structure

```
llmc/tui/
├── __init__.py
├── app.py              # Main LLMC_TUI app, navigation
├── theme.py            # Cyberpunk color scheme
├── widgets/            # Reusable components
│   ├── log_panel.py    # Live log streaming widget
│   ├── stats_panel.py  # System stats widget
│   └── result_tree.py  # Search results tree
└── screens/
    ├── dashboard.py    # Home screen (stats + quick actions)
    ├── search.py       # Search screen
    ├── service.py      # Service management
    ├── navigate.py     # Code navigation
    ├── docs.py         # Documentation generation
    ├── config.py       # Enrichment configuration
    ├── analytics.py    # Query analytics (legacy)
    └── ruta.py         # User testing (future)
```

### Screen Base Class

```python
class LLMCScreen(Screen):
    """Base class for all LLMC TUI screens."""
    
    # Standard navigation bindings
    BINDINGS = [
        ("1", "goto_dashboard", "Dashboard"),
        ("2", "goto_search", "Search"),
        ("3", "goto_service", "Service"),
        ("4", "goto_nav", "Navigate"),
        ("5", "goto_docs", "Docs"),
        ("6", "goto_ruta", "RUTA"),
        ("7", "goto_analytics", "Analytics"),
        ("8", "goto_config", "Config"),
        ("escape", "go_back", "Back"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield self.build_content()  # Subclass implements
        yield Footer()  # Standard nav bar
    
    def action_goto_dashboard(self):
        self.app.switch_screen(DashboardScreen())
    
    # ... other navigation actions
```

### CLI Integration Pattern

Each screen calls CLI service functions:

```python
# screens/service.py
from llmc.commands.service import (
    start as cli_start,
    stop as cli_stop,
    status as cli_status,
    repo_list as cli_repo_list,
)

class ServiceScreen(LLMCScreen):
    def action_start_daemon(self):
        """Start daemon - same logic as CLI."""
        try:
            cli_start()
            self.notify("✓ Daemon started", severity="information")
        except Exception as e:
            self.notify(f"✗ {e}", severity="error")
    
    def update_status(self):
        """Refresh status - same logic as CLI."""
        status = cli_status(return_dict=True)
        self.query_one("#status-panel").update(status)
```

## Cyberpunk Theme

```python
# llmc/tui/theme.py
LLMC_THEME = {
    "primary": "#00ff9f",      # Neon green
    "secondary": "#00b8ff",    # Cyan
    "accent": "#ff00ff",       # Magenta
    "warning": "#ffff00",      # Yellow
    "error": "#ff0040",        # Red
    "surface": "#0a0a0f",      # Near-black
    "panel": "#1a1a2e",        # Dark purple-gray
    "text": "#ffffff",
    "text-muted": "#666680",
}
```

## Implementation Phases

### Phase 1: Core Screens (MVP)
1. **Dashboard** - Stats + quick actions + live log
2. **Search** - Query input + results display
3. **Service** - Start/stop/status/logs

### Phase 2: Navigation & Docs
4. **Navigate** - Where-used, lineage
5. **Docs** - Generate status, trigger generation

### Phase 3: Config & Analytics
6. **Config** - Enrichment chain editor (already built!)
7. **Analytics** - Port from existing

### Phase 4: Polish
8. **RUTA** - User testing scenarios
9. Theme refinements
10. Keyboard shortcut consistency

## Success Criteria

1. **Every CLI command has a TUI equivalent**
2. **Same underlying service functions** - no logic duplication
3. **Consistent navigation** - number keys work everywhere
4. **Live updates** - logs, stats refresh automatically
5. **Retro cyberpunk vibe** - neon colors, heavy borders, ASCII art

## Migration Notes

### From Existing TUI

Keep these screens (port logic):
- `monitor.py` → becomes `dashboard.py`
- `search.py` → keep as-is, refactor to use CLI service
- `analytics.py` → keep as bonus screen
- `config.py` → merge with new enrichment config

Remove/Replace:
- `inspector.py` → merge into `navigate.py`
- `live_monitor.py` → merge into `dashboard.py`
- `rag_doctor.py` → becomes quick action on dashboard

### Testing

For each screen:
1. Verify TUI action produces same result as CLI command
2. Verify keyboard shortcuts work
3. Verify screen updates on data changes
4. Verify ESC returns to previous screen

---

**Author:** Claude  
**Date:** 2025-12-04  
**Status:** Ready for Implementation
