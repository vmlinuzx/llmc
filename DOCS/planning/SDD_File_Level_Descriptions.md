# SDD: File-Level Descriptions (Roadmap 1.2)

**Date:** 2025-12-19  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P1 (Medium)  
**Effort:** 8-12 hours  
**Assignee:** Jules  

---

## 1. Executive Summary

Add file-level descriptions to the RAG database so `mcgrep` and other tools can display stable, meaningful file summaries instead of using the first span's summary as a proxy.

Currently, `mcgrep.py` (line 407-410) extracts descriptions from the first span's summary:
```python
# Use first span's summary as file description (first sentence)
if item.summary:
    desc = item.summary.split('.')[0]  # First sentence
    file_descriptions[file_path] = desc
```

This is a stopgap. We need persistent, pre-computed file descriptions.

---

## 2. Problem Statement

- **Current state:** No `file_descriptions` table exists in the RAG database
- **Workaround:** `mcgrep` uses first span summary as proxy (unreliable)
- **Impact:** File summaries are inconsistent and depend on arbitrary span ordering

---

## 3. Implementation Tasks

### Task 1: Create Database Schema (2h)

**File:** `llmc/rag/schema.py`

Add the following table definition to the schema initialization:

```sql
CREATE TABLE IF NOT EXISTS file_descriptions (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    model TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    schema_ver TEXT
);

CREATE INDEX IF NOT EXISTS idx_file_descriptions_input_hash 
ON file_descriptions(input_hash);
```

**Acceptance Criteria:**
- [ ] Table created during `llmc repo register` or migration
- [ ] `file_id` is a foreign key to `files(id)`
- [ ] `ON DELETE CASCADE` ensures cleanup when files are removed

---

### Task 2: Implement Description Generator (4h)

**File:** `llmc/rag/enrichment/file_descriptions.py` (new file)

Create a module that generates file descriptions using two tiers:

**Tier 1 (Cheap/Default):** Compress top-K span summaries
```python
def generate_cheap_description(spans: list[Span], k: int = 3) -> str:
    """Generate description by concatenating top K span summaries."""
    summaries = [s.summary for s in spans[:k] if s.summary]
    combined = ". ".join(summaries)
    # Truncate to ~50 words
    words = combined.split()[:50]
    return " ".join(words)
```

**Tier 2 (Rich/Optional):** One LLM call per file
```python
def generate_rich_description(file_content: str, spans: list[Span], model: str) -> str:
    """Use LLM to generate a ~50 word file description."""
    prompt = f"""Summarize the purpose of this file in ~50 words.
Focus on: what it does, key exports, and how it fits the codebase.

File spans: {[s.symbol for s in spans[:5]]}

Content (first 2000 chars):
{file_content[:2000]}
"""
    return call_ollama(prompt, model=model)
```

**Staleness Detection:**
```python
def compute_input_hash(file_hash: str, span_hashes: list[str], algo_version: str) -> str:
    """Compute hash for staleness detection."""
    data = file_hash + "".join(span_hashes[:5]) + algo_version
    return hashlib.sha256(data.encode()).hexdigest()[:16]
```

**Acceptance Criteria:**
- [ ] `generate_cheap_description()` works without LLM
- [ ] `generate_rich_description()` uses Ollama (optional)
- [ ] `compute_input_hash()` enables incremental recompute
- [ ] Unit tests for both tiers

---

### Task 3: Integrate with Enrichment Pipeline (2h)

**File:** `llmc/rag/enrichment/pipeline.py`

Add a new enrichment phase that runs after span enrichment:

```python
async def enrich_file_descriptions(db: Database, repo_root: Path, mode: str = "cheap"):
    """Enrich files with descriptions.
    
    Args:
        mode: "cheap" (span compression) or "rich" (LLM per file)
    """
    files_needing_enrichment = db.query("""
        SELECT f.id, f.path, f.file_hash
        FROM files f
        LEFT JOIN file_descriptions fd ON f.id = fd.file_id
        WHERE fd.file_id IS NULL
        OR fd.input_hash != ?
    """, [current_algo_version])
    
    for file in files_needing_enrichment:
        spans = db.get_spans_for_file(file.id)
        if mode == "cheap":
            desc = generate_cheap_description(spans)
        else:
            content = (repo_root / file.path).read_text()
            desc = generate_rich_description(content, spans, model="qwen2.5:7b")
        
        db.upsert_file_description(file.id, desc, input_hash)
```

**Acceptance Criteria:**
- [ ] Runs after span enrichment in pipeline
- [ ] Only processes files that need enrichment (incremental)
- [ ] Supports `--mode cheap|rich` flag

---

### Task 4: Update mcgrep to Use Real Descriptions (2h)

**File:** `llmc/mcgrep.py`

Replace the proxy logic (lines 407-410) with database lookup:

```python
# Before (proxy):
if item.summary:
    desc = item.summary.split('.')[0]
    file_descriptions[file_path] = desc

# After (database):
def _get_file_descriptions(db: Database, file_paths: list[str]) -> dict[str, str]:
    """Fetch file descriptions from database."""
    result = {}
    for path in file_paths:
        desc = db.query_one("""
            SELECT fd.summary 
            FROM file_descriptions fd
            JOIN files f ON fd.file_id = f.id
            WHERE f.path = ?
        """, [path])
        if desc:
            result[path] = desc
    return result

# In _run_search():
file_descriptions = _get_file_descriptions(db, list(code_groups.keys()) + list(docs_groups.keys()))
```

**Acceptance Criteria:**
- [ ] Falls back to span-proxy if no description exists
- [ ] No change to mcgrep output format
- [ ] Description truncated to first sentence for compact display

---

## 4. Testing

### Unit Tests

**File:** `tests/rag/test_file_descriptions.py`

```python
def test_cheap_description_generation():
    """Test span compression produces valid description."""
    spans = [MockSpan(summary="Handles auth"), MockSpan(summary="JWT validation")]
    desc = generate_cheap_description(spans)
    assert "auth" in desc.lower() or "jwt" in desc.lower()
    assert len(desc.split()) <= 50

def test_input_hash_changes_with_content():
    """Test hash changes when file content changes."""
    h1 = compute_input_hash("abc", ["s1"], "v1")
    h2 = compute_input_hash("def", ["s1"], "v1")
    assert h1 != h2

def test_description_upsert_idempotent():
    """Test upserting same description is safe."""
    db.upsert_file_description(1, "desc", "hash")
    db.upsert_file_description(1, "desc", "hash")
    assert db.count_file_descriptions() == 1
```

### Integration Test

```bash
# Enrich a repo, verify descriptions exist
llmc repo register .
llmc rag enrich --file-descriptions
sqlite3 ~/.local/share/llmc/rag/rag.db "SELECT COUNT(*) FROM file_descriptions;"
# Should return > 0
```

---

## 5. Success Criteria

- [ ] `file_descriptions` table exists and is populated after enrichment
- [ ] `mcgrep` shows stable file summaries from database
- [ ] Enrichment is incremental (only re-processes changed files)
- [ ] No performance regression in `mcgrep` search

---

## 6. Files Modified

| File | Change |
|------|--------|
| `llmc/rag/schema.py` | Add `file_descriptions` table |
| `llmc/rag/enrichment/file_descriptions.py` | New module |
| `llmc/rag/enrichment/pipeline.py` | Add file description phase |
| `llmc/mcgrep.py` | Use database descriptions |
| `tests/rag/test_file_descriptions.py` | New test file |

---

## 7. Notes for Jules

1. **Start with Task 1 (schema)** - this unblocks everything else
2. **Task 2 is the core logic** - focus on `cheap` mode first, `rich` is optional
3. **Don't break mcgrep** - it must continue working even before descriptions exist
4. **Run tests** before submitting: `pytest tests/rag/test_file_descriptions.py`
