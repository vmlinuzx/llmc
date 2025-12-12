# Implementation Plan: Event-Driven RAG Service

**Branch:** `feature/event-driven-service`  
**Started:** 2025-12-11  
**Status:** 🚧 In Progress

---

## Summary

Replace the CPU-hungry polling loop in `tools/rag/service.py` with inotify-based file watching. Goal: ~0% CPU when idle, instant response to file changes.

---

## Implementation Checklist

### Phase 1: Core Components ✅
- [x] **1.1** Create `tools/rag/watcher.py` with `RepoWatcher` class (inotify wrapper)
- [x] **1.2** Create `ChangeQueue` class (debounced change queue with blocking wait)
- [x] **1.3** Add gitignore-aware path filtering

### Phase 2: Service Integration ✅
- [x] **2.1** Add `--mode event|poll` flag to `llmc-rag start`
- [x] **2.2** Refactor `run_loop()` to use watcher in event mode
- [x] **2.3** Keep polling mode working (backward compat)

### Phase 3: Configuration ✅
- [x] **3.1** Add `[daemon] mode = "event"` to llmc.toml
- [x] **3.2** Add `debounce_seconds` config option
- [x] **3.3** Document new config options

### Phase 4: Testing & Polish
- [ ] **4.1** Manual test: verify ~0% CPU when idle
- [ ] **4.2** Manual test: verify file change triggers processing
- [x] **4.3** Update CHANGELOG.md
- [x] **4.4** Commit (done) - push needs manual auth: `git push -u origin feature/event-driven-service`

---

## Files Changed

| File | Change Type | Notes |
|------|-------------|-------|
| `tools/rag/watcher.py` | NEW | RepoWatcher, ChangeQueue |
| `tools/rag/service.py` | MODIFY | Add event mode to run_loop() |
| `llmc.toml` | MODIFY | Add daemon.mode config |
| `CHANGELOG.md` | MODIFY | Document feature |

---

## Not Touched (Explicitly)

- `qwen_enrich_batch.py` - Enrichment script unchanged
- `EnrichmentPipeline` - Core pipeline unchanged
- `process_repo()` - Just called differently, not modified
- Database/indexes - Unchanged

---

## Notes

- Using `pyinotify` (already installed)
- Fallback to poll mode if inotify unavailable
- Debounce default: 2 seconds after last change
