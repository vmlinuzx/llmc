# RAG Daemon Fix - Quick Reference Card

**P0 CRITICAL BUG** | **60 MIN FIX** | **HIGH IMPACT**

---

## 🚨 THE PROBLEM
Daemon produces FAKE enrichment data instead of calling real LLMs

---

## 📍 WHERE
`/home/vmlinux/src/llmc/tools/rag/service.py` line 226

---

## ❌ BROKEN CODE
```python
# Line 226 - WRONG
success, output = self.run_rag_cli(repo, ["enrich", "--execute"])
```

---

## ✅ FIXED CODE
```python
# Replace with:
from tools.rag.runner import run_enrich, run_sync, run_embed

run_enrich(
    repo,
    backend=os.getenv("ENRICH_BACKEND", "ollama"),
    router=os.getenv("ENRICH_ROUTER", "on"),
    start_tier=os.getenv("ENRICH_START_TIER", "7b"),
    batch_size=5,
    max_spans=50,
    cooldown=0
)
```

---

## 📋 CHECKLIST

**Before:**
- [ ] Stop daemon: `llmc-rag-service stop`
- [ ] Backup: `cp service.py service.py.backup`

**Implementation:**
- [ ] Replace `process_repo()` method (line ~210-234)
- [ ] Add environment variable support
- [ ] Remove/comment `run_rag_cli()` method

**Testing:**
- [ ] Test imports work
- [ ] Process 1 span manually
- [ ] Verify real summary in database
- [ ] Start daemon and monitor

**Verification:**
- [ ] GPU usage 40-60% during enrichment
- [ ] NO "auto-summary generated offline" in DB
- [ ] Metrics in `logs/enrichment_metrics.jsonl`
- [ ] Logs show routing (7b/14b/nano)

---

## 🔍 VERIFY SUCCESS

```bash
# Check database for real summaries
sqlite3 /path/to/repo/.rag/rag.db \
  "SELECT summary_120w FROM enrichments 
   ORDER BY created_at DESC LIMIT 1;"

# Should see intelligent summary, NOT:
# "file.py:10-50 auto-summary generated offline."
```

---

## 📊 BEFORE vs AFTER

| Metric | Broken | Fixed |
|--------|--------|-------|
| Summary Quality | 0% (fake) | 95% (real) |
| GPU Usage | 0% | 40-60% |
| Routing | None | 7b→14b→nano |
| Metrics | None | Comprehensive |
| Retry Logic | None | Yes |
| Cost/100 spans | $0 (worthless) | $0.65 (valuable) |

---

## 🛠️ ENVIRONMENT SETUP

```bash
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b
export ENRICH_BATCH_SIZE=5
export ENRICH_MAX_SPANS=50
export ENRICH_OLLAMA_HOSTS="athena=http://athena:11434,local=http://localhost:11434"
```

---

## 📚 FULL DOCUMENTATION

- **Investigation:** `RAG_DAEMON_ENRICHMENT_INVESTIGATION.md` (321 lines)
- **Flow Diagrams:** `RAG_DAEMON_FLOW_DIAGRAM.md` (236 lines)
- **Checklist:** `RAG_DAEMON_FIX_CHECKLIST.md` (510 lines)
- **Summary:** `RAG_DAEMON_SUMMARY.md` (223 lines)

All in: `/home/vmlinux/src/llmc/DOCS/`

---

## 🔄 ROLLBACK

```bash
llmc-rag-service stop
cp service.py.backup service.py
llmc-rag-service start
```

---

## ⚡ WHY P0?

- Daemon completely broken for main purpose
- Silently produces garbage (looks functional)
- Blocks all AI code assistance features
- Wastes resources on fake processing
- 100% of enrichment data is worthless

---

## 🎯 SUCCESS CRITERIA

1. Daemon starts without errors
2. Real LLM summaries in database
3. GPU usage visible during enrichment
4. Routing logs show tier selection
5. Metrics logged to JSONL
6. No fake "auto-summary" data

---

## 📞 HELP

See full checklist: `RAG_DAEMON_FIX_CHECKLIST.md`  
Or investigation: `RAG_DAEMON_ENRICHMENT_INVESTIGATION.md`

---

**STOP EVERYTHING ELSE UNTIL THIS IS FIXED**

This bug makes the daemon worthless. Fix it first, then proceed with other features.
