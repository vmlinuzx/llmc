# RAG Incremental Enrichment Optimization

**Issue:** Changing one line in a file re-enriches the ENTIRE file  
**Impact:** Massive waste of compute, cost, and time  
**Priority:** P1 - Performance Critical

---

## Current Behavior (INEFFICIENT)

### What Happens When You Save a File:

```
1. File changes detected (e.g., edit 1 function)
2. sync() runs → replace_spans(file_id, new_spans)
3. DELETE FROM spans WHERE file_id = ?  ← Deletes ALL spans
4. INSERT all new spans (even unchanged ones)
5. Enrichments become orphaned (span_hash no longer exists)
6. pending_enrichments() finds ALL spans need enrichment
7. Re-enrich EVERY span in the file (100+ spans!)
```

**Example:**
- Edit 1 function in a 1000-line file with 50 spans
- Result: Re-enrich ALL 50 spans
- Cost: ~50 LLM calls (should be ~1-3)

---

## Root Cause

**File:** `/home/vmlinux/src/llmc/tools/rag/database.py` line 127

```python
def replace_spans(self, file_id: int, spans: Sequence[Span]) -> None:
    # ❌ PROBLEM: Deletes ALL spans for file
    self.conn.execute("DELETE FROM spans WHERE file_id = ?", (file_id,))
    
    # Then inserts all new spans
    self.conn.executemany("INSERT OR REPLACE INTO spans (...) VALUES (...)", ...)
```

**Why this is bad:**
1. Spans have unique `span_hash` based on content
2. Enrichments reference `span_hash`
3. When you delete a span, its enrichment becomes orphaned
4. Even if the span is re-inserted with same hash, the enrichment link is broken
5. `pending_enrichments()` thinks it needs enrichment

---

## The Smart Solution

### Option A: Differential Span Update (RECOMMENDED)

**Keep unchanged spans, only update/delete/insert what changed:**

```python
def replace_spans(self, file_id: int, spans: Sequence[Span]) -> None:
    """Replace spans for a file, preserving unchanged spans and their enrichments."""
    
    # Get existing span hashes for this file
    existing = self.conn.execute(
        "SELECT span_hash FROM spans WHERE file_id = ?",
        (file_id,)
    ).fetchall()
    existing_hashes = {row[0] for row in existing}
    
    # New span hashes
    new_hashes = {span.span_hash for span in spans}
    
    # Identify changes
    to_delete = existing_hashes - new_hashes  # Spans that no longer exist
    to_add = new_hashes - existing_hashes      # New spans
    unchanged = existing_hashes & new_hashes   # Keep these!
    
    # Only delete spans that actually changed or were removed
    if to_delete:
        placeholders = ','.join('?' * len(to_delete))
        self.conn.execute(
            f"DELETE FROM spans WHERE span_hash IN ({placeholders})",
            list(to_delete)
        )
    
    # Only insert truly new spans
    new_spans = [s for s in spans if s.span_hash in to_add]
    if new_spans:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO spans (
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, doc_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(file_id, s.symbol, s.kind, s.start_line, s.end_line,
              s.byte_start, s.byte_end, s.span_hash, s.doc_hint)
             for s in new_spans]
        )
    
    print(f"  📊 Span delta: {len(unchanged)} unchanged, {len(to_add)} added, {len(to_delete)} deleted")
```

**Benefits:**
- ✅ Preserves enrichments for unchanged code
- ✅ Only enriches what actually changed
- ✅ Massive compute savings (1-3 spans vs 50+)
- ✅ Faster sync operations
- ✅ Lower API costs

---

## Performance Impact

### Before (Current):
```
Edit 1 function in 50-span file:
- Sync: Delete 50 + Insert 50 = 100 DB ops
- Enrichment: 50 LLM calls (~2-5 minutes, $0.50-$2.50)
```

### After (Optimized):
```
Edit 1 function in 50-span file:
- Sync: Delete 1-3 + Insert 1-3 = 2-6 DB ops (98% reduction!)
- Enrichment: 1-3 LLM calls (~2-10 seconds, $0.01-$0.10)
```

**Savings:**
- 🔥 **~95% fewer DB operations**
- 🔥 **~95% fewer LLM calls**  
- 🔥 **~95% cost reduction**
- 🔥 **~98% time savings**

---

## Real-World Example

**Scenario:** Working on a module with 10 files, editing 1 function per file

### Current Behavior:
```
Save file 1 → Re-enrich all 50 spans (2 min)
Save file 2 → Re-enrich all 45 spans (2 min)
Save file 3 → Re-enrich all 60 spans (2.5 min)
...
Total: 500+ spans, 20+ minutes, $5-10 in API costs
```

### With Optimization:
```
Save file 1 → Enrich 2 changed spans (5 sec)
Save file 2 → Enrich 1 changed span (3 sec)
Save file 3 → Enrich 3 changed spans (8 sec)
...
Total: 15-20 spans, 1-2 minutes, $0.20-0.50 in API costs
```

**Result:** 10x-20x faster, 10x-20x cheaper!

---

## Edge Cases to Handle

### 1. Line Number Changes
**Problem:** If you add lines above a function, its line numbers change but content is same

**Solution:** `span_hash` is based on content, not line numbers, so this works correctly!

```python
# span_hash = sha256(code_content)
# Not affected by line number shifts
```

### 2. Span Splitting
**Problem:** Edit middle of large function, might split into 2 spans

**Solution:** Both new spans get new hashes → both need enrichment ✅

### 3. Span Merging  
**Problem:** Delete code between 2 functions, they merge into 1 span

**Solution:** New merged span has new hash → needs enrichment ✅

---

## Implementation Plan

### Step 1: Update `replace_spans()` method
**File:** `/home/vmlinux/src/llmc/tools/rag/database.py` line 126

Replace current implementation with differential logic above.

### Step 2: Test with real edits
```bash
# Edit one function
echo "def test(): pass" >> some_file.py

# Check what needs enrichment
python -m tools.rag.cli sync --path some_file.py
python -m tools.rag.cli enrich --dry-run

# Should only show 1-2 spans, not entire file!
```

### Step 3: Monitor metrics
```python
# Add to sync stats
{
  "spans_unchanged": 45,
  "spans_added": 2,
  "spans_deleted": 1,
  "enrichment_saved": 43  # spans that didn't need re-enrichment
}
```

---

## Additional Optimizations

### 1. Smart Cooldown
Current cooldown is file-level. Make it span-level:

```python
def pending_enrichments(self, limit: int = 32, cooldown_seconds: int = 0):
    # Check span mtime, not file mtime
    WHERE span_mtime IS NULL OR (? - span_mtime) >= ?
```

### 2. Dependency-Aware Enrichment
If function A calls function B, and B changes, maybe re-enrich A too?

**For now:** Skip this, too complex. Let users manually trigger if needed.

### 3. Batch Invalidation
If editing imports that affect many files, bulk invalidate:

```bash
python -m tools.rag.cli invalidate --pattern "src/models/*.py"
```

---

## Rollout Strategy

### Phase 1: Implement & Test (1-2 hours)
- Update `replace_spans()` method
- Add logging for span delta
- Test with various edit patterns

### Phase 2: Monitor (1 week)
- Watch enrichment counts drop
- Verify quality stays high
- Check for edge cases

### Phase 3: Document & Enable (Done!)
- Update docs
- Add to service default behavior

---

## Success Metrics

After implementation:

- [ ] Editing 1 function enriches ≤ 3 spans (not 50+)
- [ ] Sync operations 10x faster
- [ ] Enrichment API costs drop 90%+
- [ ] Quality score remains ≥ 90%
- [ ] No orphaned enrichments
- [ ] Service logs show span delta stats

---

## Priority Justification

**P1 - High Priority** because:
- Directly impacts developer productivity
- Wastes significant compute resources
- Increases API costs 10x-20x
- Makes real-time enrichment impractical
- Affects service responsiveness

**Not P0** because:
- System works, just inefficiently
- Workaround exists (disable continuous enrichment)
- Not blocking core functionality

---

## Implementation Status

- [x] Issue identified and analyzed
- [x] Solution designed
- [x] Documentation written
- [ ] Code implemented (`replace_spans()`)
- [ ] Tests written
- [ ] Deployed to service
- [ ] Metrics validated

---

**Next Step:** Implement the differential span update in `database.py`

Want me to implement this fix now? It's a ~40 line change that will make a huge difference!
