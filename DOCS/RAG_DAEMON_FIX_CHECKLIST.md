# RAG Daemon Fix - Implementation Checklist

**P0 CRITICAL FIX** - Fix daemon producing fake enrichment data  
**Target File:** `/home/vmlinux/src/llmc/tools/rag/service.py`  
**Estimated Time:** 30-60 minutes

---

## Pre-Flight Checks

- [ ] Stop running `llmc-rag-service` daemon
  ```bash
  llmc-rag-service stop
  # Or: pkill -f llmc-rag-service
  ```

- [ ] Backup current service.py
  ```bash
  cp /home/vmlinux/src/llmc/tools/rag/service.py \
     /home/vmlinux/src/llmc/tools/rag/service.py.backup
  ```

- [ ] Verify test repo exists for validation
  ```bash
  ls -la /path/to/test/repo/.rag/
  ```

---

## Implementation Steps

### Step 1: Modify `tools/rag/service.py`

**Location:** Line ~210-234 (the `process_repo` method)

#### Current Code (DELETE):
```python
def process_repo(self, repo_path: str):
    """Process one repo: sync, enrich, embed."""
    repo = Path(repo_path)
    if not repo.exists():
        print(f"⚠️  Repo not found: {repo_path}")
        return
    
    print(f"🔄 Processing {repo.name}...")
    
    # Step 1: Sync changed files (git diff based)
    success, output = self.run_rag_cli(repo, ["sync", "--since", "HEAD~1"])
    if not success:
        print(f"  ⚠️  Sync failed: {output[:100]}")
    
    # Step 2: Enrich pending spans
    success, output = self.run_rag_cli(repo, ["enrich", "--execute"])
    if not success:
        print(f"  ⚠️  Enrichment had failures")
    
    # Step 3: Embed pending spans
    success, output = self.run_rag_cli(repo, ["embed", "--execute"])
    if not success:
        print(f"  ⚠️  Embedding failed: {output[:100]}")
    
    print(f"  ✅ {repo.name} processed")
```

#### New Code (REPLACE WITH):
```python
def process_repo(self, repo_path: str):
    """Process one repo: sync, enrich, embed with REAL LLMs."""
    repo = Path(repo_path)
    if not repo.exists():
        print(f"⚠️  Repo not found: {repo_path}")
        return
    
    print(f"🔄 Processing {repo.name}...")
    
    # Import proper runner functions
    import sys
    import os
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    
    try:
        from tools.rag.runner import run_enrich, run_sync, run_embed, detect_changes
        from tools.rag.config import index_path_for_write
    except ImportError as e:
        print(f"  ⚠️  Failed to import RAG runner: {e}")
        return
    
    # Step 1: Detect and sync changed files
    try:
        index_path = index_path_for_write(repo)
        changes = detect_changes(repo, index_path=index_path)
        if changes:
            run_sync(repo, changes)
            print(f"  ✅ Synced {len(changes)} changed files")
        else:
            print(f"  ℹ️  No file changes detected")
    except Exception as e:
        print(f"  ⚠️  Sync failed: {e}")
        # Continue anyway - enrichment might still work
    
    # Step 2: Enrich pending spans with REAL LLMs
    try:
        backend = os.getenv("ENRICH_BACKEND", "ollama")
        router = os.getenv("ENRICH_ROUTER", "on")
        start_tier = os.getenv("ENRICH_START_TIER", "7b")
        batch_size = int(os.getenv("ENRICH_BATCH_SIZE", "5"))
        max_spans = int(os.getenv("ENRICH_MAX_SPANS", "50"))
        cooldown = int(os.getenv("ENRICH_COOLDOWN", "0"))
        
        print(f"  🤖 Enriching with: backend={backend}, router={router}, tier={start_tier}")
        run_enrich(
            repo,
            backend=backend,
            router=router,
            start_tier=start_tier,
            batch_size=batch_size,
            max_spans=max_spans,
            cooldown=cooldown
        )
        print(f"  ✅ Enriched pending spans with real LLM summaries")
    except Exception as e:
        print(f"  ⚠️  Enrichment failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 3: Generate embeddings for enriched spans
    try:
        embed_limit = int(os.getenv("ENRICH_EMBED_LIMIT", "100"))
        run_embed(repo, limit=embed_limit)
        print(f"  ✅ Generated embeddings (limit={embed_limit})")
    except Exception as e:
        print(f"  ⚠️  Embedding failed: {e}")
    
    print(f"  ✅ {repo.name} processing complete")
```

- [ ] Code replaced in service.py
- [ ] Verified syntax (no typos, proper indentation)

---

### Step 2: Add Environment Variable Support

Add to the top of `service.py` (after imports):

```python
# Default enrichment settings (can be overridden via environment)
DEFAULT_ENRICH_BACKEND = os.getenv("ENRICH_BACKEND", "ollama")
DEFAULT_ENRICH_ROUTER = os.getenv("ENRICH_ROUTER", "on")
DEFAULT_ENRICH_START_TIER = os.getenv("ENRICH_START_TIER", "7b")
DEFAULT_ENRICH_BATCH_SIZE = int(os.getenv("ENRICH_BATCH_SIZE", "5"))
DEFAULT_ENRICH_MAX_SPANS = int(os.getenv("ENRICH_MAX_SPANS", "50"))
DEFAULT_ENRICH_COOLDOWN = int(os.getenv("ENRICH_COOLDOWN", "0"))
DEFAULT_ENRICH_EMBED_LIMIT = int(os.getenv("ENRICH_EMBED_LIMIT", "100"))
```

- [ ] Environment variables added to service.py
- [ ] Defaults make sense for your setup

---

### Step 3: Update Daemon Startup Script

If you have a systemd service or startup script, add environment variables:

**Option A: systemd service file**
```ini
[Service]
Environment="ENRICH_BACKEND=ollama"
Environment="ENRICH_ROUTER=on"
Environment="ENRICH_START_TIER=7b"
Environment="ENRICH_BATCH_SIZE=5"
Environment="ENRICH_MAX_SPANS=50"
Environment="ENRICH_COOLDOWN=0"
Environment="ENRICH_EMBED_LIMIT=100"
Environment="ENRICH_OLLAMA_HOSTS=athena=http://athena:11434,local=http://localhost:11434"
```

**Option B: Shell startup script**
```bash
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b
export ENRICH_BATCH_SIZE=5
export ENRICH_MAX_SPANS=50
export ENRICH_COOLDOWN=0
export ENRICH_EMBED_LIMIT=100
export ENRICH_OLLAMA_HOSTS="athena=http://athena:11434,local=http://localhost:11434"

python -m tools.rag.service start
```

- [ ] Startup script updated with environment variables
- [ ] Ollama hosts configured correctly

---

### Step 4: Optional - Remove Dead Code

The `run_rag_cli` method is now unused. You can either:

**Option A: Delete it** (recommended)
```python
# Delete lines ~195-208 in service.py
def run_rag_cli(self, repo: Path, command: List[str]) -> Tuple[bool, str]:
    # ... DELETE THIS ENTIRE METHOD ...
```

**Option B: Comment it out** (safer for now)
```python
# DEPRECATED: No longer used, replaced by direct runner calls
# def run_rag_cli(self, repo: Path, command: List[str]) -> Tuple[bool, str]:
#     """Run a RAG CLI command for a repo."""
#     ...
```

- [ ] Dead code removed or commented out

---

## Testing

### Test 1: Verify Imports Work
```bash
cd /home/vmlinux/src/llmc
python3 << 'EOF'
from pathlib import Path
from tools.rag.runner import run_enrich, run_sync, run_embed, detect_changes
from tools.rag.config import index_path_for_write
print("✅ All imports successful")
EOF
```

- [ ] Imports work without errors

---

### Test 2: Dry Run on Test Repo
```bash
cd /home/vmlinux/src/llmc

# Set environment for testing
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b
export ENRICH_BATCH_SIZE=2
export ENRICH_MAX_SPANS=5
export ENRICH_COOLDOWN=0

# Test the enrichment directly
python3 scripts/qwen_enrich_batch.py \
    --repo /path/to/test/repo \
    --backend ollama \
    --router on \
    --start-tier 7b \
    --batch-size 2 \
    --max-spans 5 \
    --dry-run
```

- [ ] Dry run shows pending spans
- [ ] No errors in output

---

### Test 3: Process One Span
```bash
# Process just 1 span to verify LLM calls work
python3 scripts/qwen_enrich_batch.py \
    --repo /path/to/test/repo \
    --backend ollama \
    --router on \
    --start-tier 7b \
    --batch-size 1 \
    --max-spans 1
```

**Expected Output:**
```
Processing span 1/1...
  Tier: 7b
  Model: qwen2.5:7b-instruct-q4_K_M
  Tokens in: 342, out: 156
  Duration: 1.23s
  GPU VRAM: 4523 MiB peak
✅ Stored enrichment for span_hash_here
```

- [ ] LLM call succeeded
- [ ] Real summary generated (not "auto-summary generated offline")
- [ ] GPU usage detected
- [ ] Metrics logged

---

### Test 4: Verify Database Contains Real Data
```bash
# Check enrichment quality
sqlite3 /path/to/test/repo/.rag/rag.db << 'EOF'
.mode column
.headers on
SELECT 
    span_hash,
    substr(summary_120w, 1, 80) as summary,
    model,
    created_at
FROM enrichments
ORDER BY created_at DESC
LIMIT 3;
EOF
```

**Expected:** Real summaries, not fake ones

- [ ] Summaries are intelligent and describe actual code
- [ ] Model name is set (e.g., "qwen2.5:7b-instruct-q4_K_M")
- [ ] NOT "auto-summary generated offline"

---

### Test 5: Start Daemon and Monitor
```bash
# Start daemon
llmc-rag-service start

# Watch logs
tail -f /path/to/daemon/logs/llmc-rag-service.log

# Or check status
llmc-rag-service status
```

- [ ] Daemon starts without errors
- [ ] Logs show "Enriching with: backend=ollama, router=on, tier=7b"
- [ ] Logs show "✅ Enriched pending spans with real LLM summaries"
- [ ] No "auto-summary generated offline" in database

---

### Test 6: Monitor GPU Usage
```bash
# In another terminal, watch GPU while daemon processes
watch -n 1 nvidia-smi

# Or use nvtop if installed
nvtop
```

- [ ] GPU usage spikes during enrichment (40-60%)
- [ ] VRAM usage is reasonable (not OOM)
- [ ] GPU returns to idle between batches

---

## Rollback Plan

If something goes wrong:

```bash
# Stop daemon
llmc-rag-service stop

# Restore backup
cp /home/vmlinux/src/llmc/tools/rag/service.py.backup \
   /home/vmlinux/src/llmc/tools/rag/service.py

# Restart daemon
llmc-rag-service start
```

---

## Success Criteria

- ✅ Daemon starts without errors
- ✅ Enrichment produces real LLM summaries (not fake)
- ✅ GPU monitoring works (VRAM, temp, util tracking)
- ✅ Smart routing works (7b → 14b → nano escalation)
- ✅ Metrics logged to JSONL files
- ✅ Retry logic kicks in on failures
- ✅ Multi-host support works (if configured)
- ✅ Database contains high-quality enrichment data

---

## Post-Fix Actions

### 1. Clean Up Old Fake Data (Optional)
```bash
# Identify fake enrichments
sqlite3 /path/to/repo/.rag/rag.db << 'EOF'
SELECT COUNT(*) as fake_count
FROM enrichments
WHERE summary_120w LIKE '%auto-summary generated offline%';
EOF

# If you want to delete them and re-enrich:
sqlite3 /path/to/repo/.rag/rag.db << 'EOF'
DELETE FROM enrichments
WHERE summary_120w LIKE '%auto-summary generated offline%';
VACUUM;
EOF

# Then let daemon re-enrich those spans
```

- [ ] Old fake data identified
- [ ] Decision made: keep or delete?

---

### 2. Monitor Performance
```bash
# Check metrics log
tail -100 /home/vmlinux/src/llmc/logs/enrichment_metrics.jsonl | jq .

# Look for:
# - "tier" distribution (should see 7b, 14b, maybe nano)
# - "duration" times (should be reasonable)
# - "gpu_vram_peak_mib" (monitoring works)
# - "success": true (high success rate)
```

- [ ] Metrics look healthy
- [ ] Tier routing working
- [ ] GPU stats present

---

### 3. Update Documentation
```bash
# Add note to CHANGELOG.md
echo "## [Fixed] RAG Daemon Enrichment

- Fixed P0 bug where daemon produced fake enrichment data
- Now uses proper qwen_enrich_batch.py with routing
- Added GPU monitoring, retry logic, and comprehensive metrics
- Environment variables for configuration
" >> /home/vmlinux/src/llmc/CHANGELOG.md
```

- [ ] Changelog updated
- [ ] Roadmap.md item checked off
- [ ] Team notified (if applicable)

---

## Troubleshooting

### Issue: "ImportError: cannot import name 'run_enrich'"
**Fix:** Ensure you're running from llmc root directory and paths are correct

### Issue: "No module named 'router'"
**Fix:** The qwen_enrich_batch.py script needs the router module. Check:
```bash
ls -la /home/vmlinux/src/llmc/scripts/router.py
```

### Issue: GPU not detected
**Fix:** Check nvidia-smi works and CUDA is available to Python:
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Issue: Ollama connection refused
**Fix:** Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
# Should return JSON with model list
```

### Issue: "No spans pending enrichment"
**Fix:** Need to sync files first:
```bash
cd /path/to/repo
python -m tools.rag.cli sync --path .
python -m tools.rag.cli enrich --dry-run --limit 10
```

---

## Estimated Timeline

- **Step 1-2:** Code changes - 15 minutes
- **Step 3:** Environment setup - 5 minutes  
- **Step 4:** Cleanup - 5 minutes
- **Testing:** 30 minutes
- **Monitoring:** 15 minutes
- **Total:** 60-70 minutes

---

## Sign-Off

- [ ] Code changes made and tested
- [ ] Daemon producing real enrichment data
- [ ] GPU monitoring confirmed working
- [ ] Metrics logging to JSONL
- [ ] Documentation updated
- [ ] Roadmap item marked complete

**Fixed by:** _______________  
**Date:** _______________  
**Verified by:** _______________

---

**This fix is CRITICAL. Do not proceed with other daemon features until this is resolved.**
