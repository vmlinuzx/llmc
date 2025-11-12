# URGENT: Stop RAG Service NOW

## The Service IS Broken and Running

If you have `llmc-rag-service` running, it is:
- ❌ Running every 180 seconds (3 minutes) by default
- ❌ Processing EVERY registered repo
- ❌ Generating FAKE enrichment data for each one
- ❌ Polluting RAG indices with garbage
- ❌ Wasting CPU/GPU cycles

## Stop It Immediately

```bash
cd /home/vmlinux/src/llmc/scripts
./llmc-rag-service stop
```

Or:
```bash
# Force kill if stop doesn't work
pkill -f llmc-rag-service
```

## Check What Damage Has Been Done

```bash
# Check if service is/was running
./llmc-rag-service status

# See which repos are registered
cat ~/.llmc/rag-service.json | jq .

# For each repo, check enrichment quality
sqlite3 /path/to/repo/.rag/rag.db \
  "SELECT COUNT(*) as fake_count
   FROM enrichments
   WHERE summary_120w LIKE '%auto-summary generated offline%';"
```

## Clean Up Fake Data (Optional)

```bash
# For each affected repo:
sqlite3 /path/to/repo/.rag/rag.db << 'EOF'
-- Count fake enrichments
SELECT COUNT(*) as fake_enrichments
FROM enrichments
WHERE summary_120w LIKE '%auto-summary generated offline%';

-- DELETE THEM (only if you want to start fresh)
DELETE FROM enrichments
WHERE summary_120w LIKE '%auto-summary generated offline%';

-- Reclaim space
VACUUM;
EOF
```

## Fix BEFORE Restarting

1. **STOP** the service ✅ (done above)
2. **FIX** the code (follow `RAG_DAEMON_FIX_CHECKLIST.md`)
3. **TEST** with 1 span manually
4. **VERIFY** real summaries in database
5. **THEN** restart: `./llmc-rag-service start`

## Timeline

```
BEFORE FIX:
Every 3 minutes → Process all repos → Generate fake data → Pollute indices
                   ↓
                 BAD BAD BAD

AFTER FIX:
Every 3 minutes → Process all repos → Call real LLMs → Quality enrichment
                   ↓
                 GOOD GOOD GOOD
```

## Priority

**DO NOT restart the service until the fix is implemented!**

The service loop will continue to:
- Waste compute every 3 minutes
- Generate 100% fake data
- Make your RAG indices worthless

---

**STOP → FIX → TEST → START**

In that order. No exceptions.
