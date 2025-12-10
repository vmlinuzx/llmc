# HLD: Opportunistic Daemon Docgen

**Date:** 2025-12-09
**Status:** Draft
**Objective:** Integrate Docgen v2 into the RAG service daemon to generate documentation during idle cycles.

---

## 1. Executive Summary

Currently, `llmc docs generate` must be run manually. This feature moves documentation generation into the background `llmc-rag-service`.

To prevents system overload, Docgen will operate in **Opportunistic Mode**:
1. It only runs if the primary enrichment loop (Sync/Enrich/Embed) is **idle**.
2. It processes exactly **one file** per cycle.
3. It immediately yields control back to the main loop to check for high-priority tasks (file changes, new spans).

---

## 2. The "One More Thing" Algorithm

The integration point is inside `tools/rag/service.py :: process_repo`.

### Current Flow
1. Sync (Git/FS check)
2. Enrich (LLM)
3. Embed (Vectors)
4. Quality Check
5. Graph Build
6. Vacuum

### Proposed Flow
```python
def process_repo(self, repo_path):
    work_done = False
    
    # 1. High Priority Tasks
    if run_sync(): work_done = True
    if run_enrich(): work_done = True
    if run_embed(): work_done = True
    
    # 2. Opportunistic Docgen (Only if idle)
    if not work_done and config.docgen.daemon_enabled:
        # "Just one more thing..."
        doc_result = docgen_orchestrator.process_next(limit=1)
        
        if doc_result.processed > 0:
            print(f"  📝 [Docgen] Generated doc for {doc_result.files[0]}")
            # We did work, so we don't want to backoff sleep completely, 
            # BUT we also don't want to claim 'work_done' in a way that 
            # prevents the daemon from sleeping at all if that's preferred.
            
            # DECISION: Treating Docgen as 'work' keeps the daemon awake 
            # and responsive, effectively churning through docs 1-by-1 
            # as fast as the interval allows.
            work_done = True 
            
    return work_done
```

---

## 3. Configuration Updates

We need to control this behavior in `llmc.toml`:

```toml
[docs.docgen]
enabled = true
backend = "shell"

# NEW: Daemon integration settings
daemon_enabled = true       # Enable background generation
daemon_priority = "idle"    # Only run when idle (future proofing)
```

---

## 4. Efficient Candidate Selection

We cannot scan 10,000 files every 3 seconds to find one missing doc. We need a performant selection strategy.

### Strategy: "Random Seek" (Stateless)
We want to avoid maintaining complex state in the daemon.

1. **Query RAG DB:** Select random file paths from `files` table (sample size ~10).
2. **Check FS:** For each candidate, check if `DOCS/REPODOCS/{path}.md` exists and is fresh (SHA match).
3. **Pick First Missing/Stale:** The first candidate that needs docs wins.
4. **Generate:** Process that one file.
5. **Abort:** If all 10 candidates have docs, assume we are mostly done and yield.

**Why Random?**
- O(1) complexity.
- No "stuck" queue (if one file fails, we won't retry it forever).
- Eventually consistent coverage.
- No new database tables needed.

---

## 5. Technical Components

### 5.1 `DocgenOrchestrator.process_opportunistic(limit=1)`

A new method on the Orchestrator optimized for the daemon:
- Does **not** load the full `rag_graph.json` (too heavy for 1 file).
- Loads graph context **JIT** (Just-In-Time) for the selected file only.
- Uses the Random Seek strategy.

### 5.2 Service Loop Integration
- Update `tools/rag/service.py` to initialize `DocgenOrchestrator` if enabled.
- Inject the logic after the embedding step.

---

## 6. Edge Cases & Risks

| Risk | Mitigation |
|------|------------|
| **VRAM Thrashing** | If Docgen uses a different model than Enrichment, interleaving them causes constant loading/unloading. **Mitigation:** Rely on `keep_alive` setting in Ollama (default 5m) to keep the large Docgen model resident across loop ticks. The "1 item" strategy relies on the model *staying* loaded. |
| **Docgen takes too long** | The shell backend has a timeout (default 60s). Logic enforces `limit=1`. |
| **Race Conditions** | Docgen already uses file locks (`.llmc/locks/docgen.lock`). If manual CLI is running, daemon will skip. |
| **Resource Contention** | Docgen runs only when Enrichment/Embed is idle. `os.nice` keeps priority low. |
| **Infinite Loop** | If a file fails to generate, we shouldn't retry it forever. The Random Seek strategy naturally distributes retries. |

---

## 7. Migration Plan

1. **Update Config:** Add `daemon_enabled` to `llmc.toml` template.
2. **Update Orchestrator:** Implement `process_opportunistic`.
3. **Update Service:** Wire it into `process_repo`.
4. **Verify:** Run daemon, watch logs for "📝 [Docgen]" entries during idle periods.
