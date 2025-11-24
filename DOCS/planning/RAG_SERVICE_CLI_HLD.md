# LLMC RAG Service CLI - High Level Design
**Author:** DC & Claude (Otto)  
**Date:** 2024-11-24  
**Status:** DRAFT - AWAITING DC APPROVAL  
**Branch:** CoupDeGras

---

## 1. Purpose & Context

This is THE front door to LLMC. The interface users interact with to manage RAG enrichment.

**Emotional Context:**  
DC has been watching these logs scroll for 3 months, perfecting every emoji, timing format, and detail. This logging system is sacred and represents months of refinement. Previous refactors (3 attempts) were rolled back after wasted days. This time we get it right.

**Core Principle:**  
**ZERO CHANGES TO LOGGING FORMAT.** The logging that goes to DC's "matrix" screen stays exactly as it is.

---

## 2. Current State

### File Structure:
```
scripts/llmc-rag-service          # Thin wrapper (17 lines)
  └─> tools/rag/service.py        # Main orchestrator (699 lines)
        └─> tools/rag/runner.py    # Calls enrichment scripts
              └─> scripts/qwen_enrich_batch.py  # THE SACRED LOGGING (line 1994)
```

### What Works:
✅ Logging format is perfected  
✅ Enrichment pipeline works  
✅ Basic commands (start/stop/status/register/unregister)  
✅ Failure tracking  
✅ Quality checks

### What's Missing:
❌ Proper systemd daemon (currently uses fork())  
❌ `health` command (check Ollama endpoints)  
❌ `logs` command (tail service output)  
❌ `config` command (show settings)  
❌ Beautiful help screen  
❌ Singular interface (user shouldn't know about 3 files)

---

## 3. Design Goals

### 3.1 User Experience
**ONE command to rule them all:**
```bash
llmc-rag <subcommand>
```

**No user should ever directly invoke:**
- `tools/rag/service.py`
- `tools/rag/runner.py`  
- `scripts/qwen_enrich_batch.py`

### 3.2 Logging Requirements (SACRED)

**The Current Logging Format MUST BE PRESERVED:**
```
Stored enrichment 0: tools/rag/quality_check/__init__.py:77-87 (13.67s) via tier 14b (qwen2.5:14b-instruct-q4_K_M)
Stored enrichment 1: tools/rag/runner.py:101-130 (3.19s) via tier 7b (qwen2.5:7b-instruct) [chain=athena, backend=athena, url=http://192.168.5.20:11434]
```

**Elements that MUST remain:**
- ✅ Enrichment counter (`0:`, `1:`)
- ✅ File path with line range (`path:77-87`)
- ✅ Timing in seconds (`(13.67s)`)
- ✅ Tier information (`via tier 14b`, `via tier 7b`)
- ✅ Model name in parentheses (`(qwen2.5:14b-instruct-q4_K_M)`)
- ✅ Chain/backend/url metadata (`[chain=athena, backend=athena, url=...]`)
- ✅ Progress indicators (`[rag-enrich] Enriched span 10/50 for tools/rag/runner.py`)
- ✅ All emojis: 🚀, 🔄, ✅, 🤖, ⚠️, 💤, 👋, 📊

**Where Logging Originates:**
- `scripts/qwen_enrich_batch.py` line 1994 (primary enrichment log)
- `tools/rag/service.py` (orchestration logs)
- `tools/rag/runner.py` (sync logs)

**Architecture Decision:**  
Logging stays IN the enrichment scripts. The service CLI just pipes stdout/stderr through naturally. NO INTERCEPTION, NO MODIFICATION.

---

## 4. Proposed Architecture

### 4.1 File Structure (NEW)

```
scripts/llmc-rag                    # Main CLI entry point (SINGULAR INTERFACE)
  └─> tools/rag/service.py          # Service orchestration (enhanced)
        ├─> tools/rag/service_daemon.py  # Systemd integration (NEW)
        ├─> tools/rag/service_health.py  # Health checks (NEW)
        └─> tools/rag/runner.py      # Enrichment pipeline (UNCHANGED)
              └─> scripts/qwen_enrich_batch.py  # Sacred logging (UNTOUCHED)
```

### 4.2 Command Structure

```bash
llmc-rag                    # Show beautiful help screen
llmc-rag help               # Same as above

# Core service commands
llmc-rag start              # Start as systemd service
llmc-rag stop               # Stop service
llmc-rag restart            # Restart service
llmc-rag status             # Show service + repo status
llmc-rag logs [-f]          # Tail service logs (journalctl wrapper)

# Repository management
llmc-rag repo add <path>    # Register repo
llmc-rag repo remove <path> # Unregister repo
llmc-rag repo list          # List all registered repos

# Health & diagnostics
llmc-rag health             # Check Ollama endpoints
llmc-rag config             # Show current configuration
llmc-rag failures [--repo <path>]  # Show failure cache
llmc-rag failures clear [--repo <path>]  # Clear failures

# Advanced
llmc-rag interval <seconds> # Change cycle interval
llmc-rag force-cycle        # Trigger immediate enrichment cycle
llmc-rag exorcist <path>    # Nuclear option: completely rebuild RAG database
```

### 4.3 Systemd Integration

**Service File:** `~/.config/systemd/user/llmc-rag.service`

```ini
[Unit]
Description=LLMC RAG Enrichment Service
After=network.target

[Service]
Type=simple
ExecStart=/home/vmlinux/src/llmc/scripts/llmc-rag _daemon_loop
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

**How it works:**
1. `llmc-rag start` → `systemctl --user start llmc-rag`
2. Systemd calls `llmc-rag _daemon_loop` (internal command)
3. Logs go to journalctl (accessed via `llmc-rag logs`)
4. `llmc-rag stop` → `systemctl --user stop llmc-rag`

**Benefits:**
- ✅ Proper daemon (no fork() hacks)
- ✅ Auto-restart on crash
- ✅ Logs managed by systemd
- ✅ `systemctl --user enable llmc-rag` for boot persistence

### 4.4 The Exorcist Command (Nuclear Option)

**Purpose:** Complete RAG database rebuild for a repo. Deletes everything and starts fresh.

**Use cases:**
- Schema changes in RAG system
- Database corruption
- Testing with fresh enrichment settings
- "It's broken and I don't know why"

**Safety Protocol (THE RITUAL):**

```bash
$ llmc-rag exorcist /home/vmlinux/src/llmc

⚠️  EXORCIST MODE: NUCLEAR OPTION ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This will PERMANENTLY DELETE the RAG database for:
  📁 /home/vmlinux/src/llmc

What you'll lose:
  • 1,247 indexed spans
  • 856 enriched summaries (months of LLM work)
  • 856 embeddings
  • All failure tracking
  • All quality metrics

This cannot be undone. The database will be rebuilt from scratch.

Press Ctrl+C now to abort...

Continuing in 5 seconds... (Ctrl+C to abort)
4...
3...
2...
1...

Type the repo name to confirm: llmc
> llmc

✅ Confirmed. Nuking RAG database...
🗑️  Deleted .rag/rag_index.db (45.2 MB)
🗑️  Deleted .rag/enrichments.json
🗑️  Deleted .rag/embeddings.db
✅ Database exorcised. Run enrichment to rebuild.

Next steps:
  llmc-rag force-cycle    # Start immediate rebuild
```

**Implementation safeguards:**
1. **Stats display** - Show exactly what will be lost (span count, enrichment count, etc.)
2. **5-second countdown** - Gives user time to panic and Ctrl+C
3. **Name confirmation** - Must type the repo name (or basename) to proceed
4. **Dry-run option** - `llmc-rag exorcist --dry-run <path>` shows what would be deleted
5. **Service check** - Refuses to run if service is currently processing that repo

**What gets deleted:**
```
<repo>/.rag/rag_index.db          # Main index
<repo>/.rag/enrichments.json      # Enrichment metadata
<repo>/.rag/embeddings.db         # Vector embeddings
<repo>/.rag/quality_reports/      # Quality check history
<repo>/.rag/failures.db           # Failure tracking (optional keep?)
```

**What's preserved:**
```
<repo>/.rag/logs/                 # Historical logs (optional)
<repo>/.rag/config/               # User config (preserved)
```

**Error conditions:**
- Service is running and processing this repo → refuse
- Repo not registered → warn but allow (orphaned database cleanup)
- Database doesn't exist → inform user "nothing to exorcise"

---

## 5. Help Screen Design

```
LLMC RAG Service
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The intelligent RAG enrichment daemon for LLMC

Usage:
  llmc-rag <command> [options]

Service Management:
  start                Start the RAG service (systemd daemon)
  stop                 Stop the RAG service
  restart              Restart the RAG service
  status               Show service status and repo details
  logs [-f]            View service logs (use -f to follow)

Repository Management:
  repo add <path>      Register a repository for enrichment
  repo remove <path>   Unregister a repository
  repo list            List all registered repositories

Health & Diagnostics:
  health               Check Ollama endpoint availability
  config               Show current service configuration
  failures             Show failure cache
  failures clear       Clear failure cache (optionally per repo)

Advanced:
  interval <seconds>   Change enrichment cycle interval
  force-cycle          Trigger immediate enrichment cycle
  exorcist <path>      Nuclear option: completely rebuild RAG database

Examples:
  llmc-rag repo add /home/you/src/llmc
  llmc-rag start
  llmc-rag logs -f
  llmc-rag health
  llmc-rag status

For detailed help: llmc-rag help <command>
```

---

## 6. Implementation Plan

### Phase 1: Systemd Integration
- [ ] Create `tools/rag/service_daemon.py`
- [ ] Generate systemd service file
- [ ] Implement `_daemon_loop` internal command
- [ ] Update `start/stop/restart` to use systemctl

### Phase 2: Enhanced Commands
- [ ] Create `tools/rag/service_health.py` for health checks
- [ ] Implement `logs` command (journalctl wrapper)
- [ ] Implement `config` command (show env + TOML settings)
- [ ] Refactor `register/unregister` → `repo add/remove`
- [ ] Implement `exorcist` command with safety protocol

### Phase 3: Polish
- [ ] Beautiful help screen with colors/formatting
- [ ] Per-command help (`llmc-rag help start`)
- [ ] Input validation and friendly error messages
- [ ] Smoke testing

### Phase 4: Documentation
- [ ] Update README with new CLI
- [ ] Migration guide for existing users
- [ ] Systemd troubleshooting guide

---

## 7. Testing Strategy

### 7.1 Logging Verification
**CRITICAL:** After each phase, verify logging output is IDENTICAL:

```bash
# Before changes
llmc-rag start
tail -f ~/.llmc/logs/rag-daemon/rag-service.log | grep "Stored enrichment"

# After changes  
llmc-rag start
llmc-rag logs -f | grep "Stored enrichment"

# MUST BE BYTE-FOR-BYTE IDENTICAL
```

### 7.2 Smoke Tests
- [ ] Start/stop service
- [ ] Register repo, trigger cycle, verify enrichment
- [ ] Check logs appear correctly
- [ ] Health command detects Ollama
- [ ] Systemd service survives reboot
- [ ] Exorcist command with Ctrl+C abort
- [ ] Exorcist command with full nuke + rebuild

---

## 8. Rollback Plan

If anything breaks:
```bash
git revert <commit>
systemctl --user stop llmc-rag
rm ~/.config/systemd/user/llmc-rag.service
systemctl --user daemon-reload
```

Old interface remains in tools/rag/service.py as fallback.

---

## 9. Open Questions for DC

1. **Systemd vs manual daemon?**  
   - Systemd is standard on Ubuntu 24, gives us proper daemon management
   - Alternative: keep fork() approach but enhance it?

2. **Log destination?**  
   - Current: Fork-based daemon writes to ~/.llmc/logs/rag-daemon/rag-service.log
   - Proposed: Systemd writes to journalctl, accessed via `llmc-rag logs`
   - Keep both? Journalctl only?

3. **Command naming?**  
   - `llmc-rag repo add` vs `llmc-rag register`?
   - `llmc-rag logs` vs `llmc-rag tail`?

4. **Auto-start on boot?**  
   - Should `llmc-rag start` also run `systemctl --user enable llmc-rag`?
   - Or separate `llmc-rag enable` command?

5. **Backwards compatibility?**  
   - Keep old `llmc-rag-service` command as alias?
   - Or clean break?

---

## 10. Success Criteria

✅ User only ever types `llmc-rag <something>`  
✅ Logging format is EXACTLY THE SAME  
✅ Service runs as proper systemd daemon  
✅ Beautiful help screen  
✅ All health/logs/config commands work  
✅ DC can watch his matrix screen without changes  
✅ No wasted days, no rollbacks

---

**DC: Please review and provide feedback on:**
- Overall architecture
- Systemd approach
- Command naming
- Any concerns about logging preservation
- Open questions above

**Do NOT proceed with implementation until DC approves this HLD.**
