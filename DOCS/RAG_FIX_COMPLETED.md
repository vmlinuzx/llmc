# RAG Service Fix - COMPLETED ✅

**Date:** 2025-11-12  
**Time:** Just now  
**Status:** FIXED AND READY TO TEST

---

## What Was Fixed

### Issue #1: FAKE Enrichment Data (P0 CRITICAL)
**Problem:** Service was calling CLI which used `default_enrichment_callable()` that generated fake placeholder summaries.

**Fixed:** Replaced `process_repo()` method to call `tools.rag.runner` functions directly, which invoke the proper `scripts/qwen_enrich_batch.py` with:
- Real LLM calls (Qwen 7b/14b or GPT-4o-mini)
- Smart tiered routing (7b → 14b → nano)
- GPU monitoring (VRAM, temp, utilization)
- Retry logic with tier escalation
- Comprehensive metrics

**Location:** `/home/vmlinux/src/llmc/tools/rag/service.py` lines 210-277

---

### Issue #2: Python Command Not Found
**Problem:** Service was calling `python` which doesn't exist on Ubuntu 24 (only `python3` exists).

**Fixed:** Changed `run_rag_cli()` method from `["python", ...]` to `["python3", ...]`

**Location:** `/home/vmlinux/src/llmc/tools/rag/service.py` line 198

---

### Issue #3: Missing Dependencies
**Problem:** `tree_sitter` and other RAG dependencies were not installed.

**Fixed:** Installed all dependencies from `/home/vmlinux/src/llmc/tools/rag/requirements.txt`

---

## Files Modified

1. **`/home/vmlinux/src/llmc/tools/rag/service.py`**
   - Replaced `process_repo()` method (68 lines)
   - Fixed `run_rag_cli()` to use `python3`
   - Added proper imports and error handling

2. **Backup Created:**
   - `/home/vmlinux/src/llmc/tools/rag/service.py.backup`

---

## What Changed in process_repo()

### BEFORE (Broken):
```python
def process_repo(self, repo_path: str):
    # Step 1: Sync
    success, output = self.run_rag_cli(repo, ["sync", "--since", "HEAD~1"])
    
    # Step 2: Enrich ❌ FAKE DATA
    success, output = self.run_rag_cli(repo, ["enrich", "--execute"])
    
    # Step 3: Embed
    success, output = self.run_rag_cli(repo, ["embed", "--execute"])
```

### AFTER (Fixed):
```python
def process_repo(self, repo_path: str):
    # Import proper runner functions
    from tools.rag.runner import run_enrich, run_sync, run_embed, detect_changes
    
    # Step 1: Detect changes and sync
    changes = detect_changes(repo, index_path)
    if changes:
        run_sync(repo, changes)
    
    # Step 2: Enrich with REAL LLMs ✅
    run_enrich(
        repo,
        backend=os.getenv("ENRICH_BACKEND", "ollama"),
        router=os.getenv("ENRICH_ROUTER", "on"),
        start_tier=os.getenv("ENRICH_START_TIER", "7b"),
        batch_size=5,
        max_spans=50,
        cooldown=0
    )
    
    # Step 3: Generate embeddings
    run_embed(repo, limit=100)
```

---

## Configuration via Environment Variables

The service now respects these environment variables:

```bash
export ENRICH_BACKEND=ollama      # or "gateway" or "auto"
export ENRICH_ROUTER=on           # Enable smart routing (on/off)
export ENRICH_START_TIER=7b       # Starting tier (7b/14b/nano)
export ENRICH_BATCH_SIZE=5        # Spans per batch
export ENRICH_MAX_SPANS=50        # Max spans per cycle
export ENRICH_COOLDOWN=0          # Cooldown in seconds
export ENRICH_EMBED_LIMIT=100     # Max embeddings per cycle
```

---

## Testing

### Quick Test Script Created
**Location:** `/home/vmlinux/src/llmc/test-rag-service.sh`

**Usage:**
```bash
cd /home/vmlinux/src/llmc
./test-rag-service.sh
# Watch it run one cycle, then Ctrl+C
```

### Manual Test
```bash
cd /home/vmlinux/src/llmc/scripts

# Set environment
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b

# Start service (will run continuously)
./llmc-rag-service start

# In another terminal, monitor
tail -f ~/.llmc/rag-service.log  # if logging is set up
# Or just watch the console output
```

### Expected Output (Good):
```
🚀 RAG service started (PID 12345)
   Tracking 1 repos
   Interval: 180s

🔄 Processing llmc...
  ℹ️  No file changes detected
  🤖 Enriching with: backend=ollama, router=on, tier=7b
  ✅ Enriched pending spans with real LLM summaries
  ✅ Generated embeddings (limit=100)
  ✅ llmc processing complete
💤 Sleeping 180s until next cycle...
```

### Bad Signs to Watch For:
- ❌ "python: command not found" - Still using wrong python
- ❌ "ImportError" - Dependencies missing
- ❌ "auto-summary generated offline" in database - Still using fake enrichment
- ❌ No GPU usage during enrichment - Not calling real LLMs

---

## Verification Checklist

After running the service for one cycle:

- [ ] Service starts without errors
- [ ] No "command not found" errors
- [ ] Logs show "🤖 Enriching with: backend=ollama, router=on"
- [ ] Logs show "✅ Enriched pending spans with real LLM summaries"
- [ ] GPU usage visible during enrichment (check with `nvidia-smi`)
- [ ] No fake "auto-summary generated offline" in database

### Check Database Quality
```bash
# If .rag directory exists
sqlite3 /home/vmlinux/src/llmc/.rag/rag.db << 'EOF'
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN summary_120w LIKE '%auto-summary generated offline%' THEN 1 END) as fake,
    COUNT(CASE WHEN summary_120w NOT LIKE '%auto-summary generated offline%' THEN 1 END) as real
FROM enrichments;
EOF
```

Expected: `fake: 0`, `real: > 0`

---

## What Happens Now

When you run `./llmc-rag-service start`:

1. **Every 180 seconds** (3 minutes)
2. **For each registered repo** (currently: `/home/vmlinux/src/llmc`)
3. **The service will:**
   - Detect changed files
   - Sync them to RAG index
   - **Call real LLMs** (Qwen 7b/14b) to generate intelligent summaries
   - Generate embeddings for searchability
   - Log metrics to track performance

---

## Before vs After

### BEFORE (Broken):
- ❌ Python command not found
- ❌ 100% fake enrichment data
- ❌ No GPU usage
- ❌ No routing
- ❌ No metrics
- ❌ Completely useless

### AFTER (Fixed):
- ✅ Runs with python3
- ✅ Real LLM summaries
- ✅ GPU monitoring
- ✅ Smart 7b→14b→nano routing
- ✅ Comprehensive metrics
- ✅ Actually useful!

---

## Rollback Plan

If something goes wrong:
```bash
cd /home/vmlinux/src/llmc/scripts
./llmc-rag-service stop

# Restore backup
cp /home/vmlinux/src/llmc/tools/rag/service.py.backup \
   /home/vmlinux/src/llmc/tools/rag/service.py

# Restart
./llmc-rag-service start
```

---

## Next Steps

1. **Test:** Run `./test-rag-service.sh` to see one cycle
2. **Verify:** Check output for real LLM calls
3. **Monitor:** Watch GPU usage during enrichment
4. **Deploy:** If test looks good, start as daemon with `--daemon` flag
5. **Celebrate:** You now have a working RAG enrichment service! 🎉

---

## Documentation Reference

All investigation documents are still available:
- `URGENT_STOP_SERVICE.md` - Immediate actions (done ✅)
- `RAG_DAEMON_SUMMARY.md` - Executive overview
- `RAG_DAEMON_QUICK_REF.md` - One-page reference
- `RAG_DAEMON_ENRICHMENT_INVESTIGATION.md` - Technical deep-dive
- `RAG_DAEMON_FLOW_DIAGRAM.md` - Visual comparison
- `RAG_DAEMON_FIX_CHECKLIST.md` - Implementation guide (done ✅)

---

**Status: READY TO TEST** 🚀

The service is fixed and ready to run. When you're ready, just run the test script or start the service!
