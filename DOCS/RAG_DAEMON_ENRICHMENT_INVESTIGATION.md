# RAG Daemon Enrichment Investigation Report

**Status:** CRITICAL P0 BUG CONFIRMED 🚨  
**Date:** 2025-11-12  
**Investigator:** Otto (Claude Sonnet 4.5)

---

## Executive Summary

The `llmc-rag-service` daemon is **completely broken** for enrichment tasks. It produces 100% useless fake data instead of calling real LLMs for code analysis. This defeats the entire purpose of the RAG enrichment system and wastes compute resources on garbage data.

---

## The Problem

### What's Happening
The daemon calls `rag enrich --execute` through the CLI, which uses `default_enrichment_callable()` that generates **FAKE placeholder summaries** like:
```
"path/to/file.py:10-50 auto-summary generated offline."
```

Instead of actual intelligent summaries from Qwen models describing what the code does.

### Root Cause
**File:** `/home/vmlinux/src/llmc/tools/rag/service.py` line 226  
**Method:** `process_repo()`

```python
# Step 2: Enrich pending spans
success, output = self.run_rag_cli(repo, ["enrich", "--execute"])
if not success:
    print(f"  ⚠️  Enrichment had failures")
```

This calls the CLI which eventually hits:

**File:** `/home/vmlinux/src/llmc/tools/rag/cli.py` line 176
```python
llm = default_enrichment_callable(model)
successes, errors = execute_enrichment(db, repo_root, llm, limit=limit, model=model, cooldown_seconds=cooldown)
```

**File:** `/home/vmlinux/src/llmc/tools/rag/workers.py` lines 209-229
```python
def default_enrichment_callable(model: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _call(prompt: Dict[str, Any]) -> Dict[str, Any]:
        path = prompt.get("path", "")
        start, end = prompt.get("lines", [0, 0])
        code: str = prompt.get("code", "")
        lines = code.splitlines()
        snippet = "\n".join(lines[:12]) if lines else None
        summary = f"{path}:{start}-{end} auto-summary generated offline."  # ❌ FAKE DATA
        return {
            "summary_120w": summary,  # ❌ WORTHLESS
            "inputs": [],              # ❌ EMPTY
            "outputs": [],             # ❌ EMPTY
            "side_effects": [],        # ❌ EMPTY
            "pitfalls": [],            # ❌ EMPTY
            "usage_snippet": snippet,
            "evidence": [{"field": "summary_120w", "lines": [start, end]}],
            "model": model,
            "schema_version": "enrichment.v1",
            "tags": [],
        }
    return _call
```

---

## What's Lost By Using The Wrong Path

The proper enrichment script `scripts/qwen_enrich_batch.py` has **1,407 lines** of sophisticated logic including:

### 1. **Smart Tiered Routing** (7b → 14b → nano)
- Analyzes code complexity (line count, nesting depth, schema depth)
- Routes simple spans to fast 7b models
- Escalates complex spans to 14b models
- Falls back to GPT-4o-mini (nano) for edge cases
- Current CLI path: **LOST** ❌

### 2. **GPU Monitoring**
- Real-time VRAM tracking
- Temperature monitoring
- Utilization stats
- Performance metrics
- Current CLI path: **LOST** ❌

### 3. **Retry Logic With Fallback**
- Automatic retry on failures
- Tier escalation on schema validation errors
- Host failover for multi-GPU setups
- Current CLI path: **LOST** ❌

### 4. **Comprehensive Metrics**
- Token counting (input/output)
- Duration tracking
- Success/failure classification
- JSONL logging for analysis
- Current CLI path: **LOST** ❌

### 5. **Multi-Host Support**
- Load balancing across multiple Ollama instances
- Athena GPU failover
- Current CLI path: **LOST** ❌

---

## The Better Alternative

### Option A: Use `tools.rag.runner.refresh` (RECOMMENDED)

**File:** `/home/vmlinux/src/llmc/tools/rag/runner.py` line 273-312  
**Function:** `command_refresh()`

This is a **proper orchestration layer** that:
1. Detects changed files
2. Syncs them to RAG index
3. Calls `run_enrich()` which invokes `scripts/qwen_enrich_batch.py` correctly
4. Runs embeddings
5. Updates stats

**Key Code:**
```python
def run_enrich(repo_root: Path, backend: str, router: str, start_tier: str, 
               batch_size: int, max_spans: int, cooldown: int) -> None:
    script = repo_root / "scripts" / "qwen_enrich_batch.py"
    cmd = _python_env() + [
        str(script),
        "--repo", str(repo_root),
        "--backend", backend,
        "--batch-size", str(batch_size),
        "--router", router,
        "--start-tier", start_tier,
        "--max-spans", str(max_spans),
    ]
    if cooldown:
        cmd.extend(["--cooldown", str(cooldown)])
    env = os.environ.copy()
    env.update({"LLM_DISABLED": "false", "NEXT_PUBLIC_LLM_DISABLED": "false"})
    subprocess.run(cmd, cwd=repo_root, check=True, env=env)
```

### Option B: Call `qwen_enrich_batch.py` Directly

The daemon could call the enrichment script directly:
```python
import subprocess
from pathlib import Path

script = repo / "scripts" / "qwen_enrich_batch.py"
result = subprocess.run(
    ["python", str(script), 
     "--repo", str(repo),
     "--backend", "ollama",  # or "gateway" or "auto"
     "--router", "on",
     "--start-tier", "7b",
     "--batch-size", "5",
     "--max-spans", "50"],
    cwd=repo,
    capture_output=True,
    text=True,
    timeout=3600  # 1 hour for batch processing
)
```

---

## Recommended Fix

### Step 1: Modify `tools/rag/service.py`

Replace the CLI call with proper runner integration:

```python
def process_repo(self, repo_path: str):
    """Process one repo: sync, enrich, embed."""
    repo = Path(repo_path)
    if not repo.exists():
        print(f"⚠️  Repo not found: {repo_path}")
        return
    
    print(f"🔄 Processing {repo.name}...")
    
    # Import the runner module
    import sys
    sys.path.insert(0, str(repo))
    from tools.rag.runner import run_sync, run_enrich, run_embed, detect_changes
    from tools.rag.config import index_path_for_write
    
    # Step 1: Detect and sync changed files
    index_path = index_path_for_write(repo)
    changes = detect_changes(repo, index_path=index_path)
    if changes:
        try:
            run_sync(repo, changes)
            print(f"  ✅ Synced {len(changes)} changed files")
        except Exception as e:
            print(f"  ⚠️  Sync failed: {e}")
    
    # Step 2: Enrich pending spans with REAL LLMs
    try:
        run_enrich(
            repo,
            backend=os.getenv("ENRICH_BACKEND", "ollama"),
            router=os.getenv("ENRICH_ROUTER", "on"),  # Enable routing!
            start_tier=os.getenv("ENRICH_START_TIER", "7b"),
            batch_size=5,
            max_spans=50,  # Process in chunks
            cooldown=0
        )
        print(f"  ✅ Enriched spans with real LLM summaries")
    except Exception as e:
        print(f"  ⚠️  Enrichment failed: {e}")
    
    # Step 3: Embed pending spans
    try:
        run_embed(repo, limit=100)
        print(f"  ✅ Generated embeddings")
    except Exception as e:
        print(f"  ⚠️  Embedding failed: {e}")
    
    print(f"  ✅ {repo.name} processed")
```

### Step 2: Remove the broken `run_rag_cli` calls

Delete or comment out lines 220-234 in `service.py` that use the CLI approach.

### Step 3: Add environment variables for configuration

Update the daemon startup to set:
```bash
export ENRICH_BACKEND=ollama  # or "gateway" or "auto"
export ENRICH_ROUTER=on       # Enable smart routing
export ENRICH_START_TIER=7b   # Start with fast 7b model
export ENRICH_OLLAMA_HOSTS="athena=http://athena:11434,local=http://localhost:11434"
```

---

## Testing Plan

### Before Fix
```bash
# Start daemon
llmc-rag-service start

# Check enrichment results (will be fake)
sqlite3 /path/to/repo/.rag/rag.db "SELECT summary_120w FROM enrichments LIMIT 5;"
# Expected: "path/to/file.py:10-50 auto-summary generated offline."
```

### After Fix
```bash
# Start daemon with fix
llmc-rag-service start

# Check enrichment results (should be real)
sqlite3 /path/to/repo/.rag/rag.db "SELECT summary_120w FROM enrichments ORDER BY created_at DESC LIMIT 5;"
# Expected: Actual intelligent summaries describing code functionality
```

### Metrics to Monitor
- Enrichment quality (summaries make sense)
- GPU utilization (should be >0% when processing)
- Processing time per span
- Tier distribution (should see 7b/14b/nano routing)
- Retry rates
- Success/failure ratios

---

## Impact Assessment

### Current State (BROKEN)
- ❌ 100% fake enrichment data
- ❌ Zero GPU utilization
- ❌ No smart routing
- ❌ No metrics
- ❌ No retry logic
- ❌ Wasted compute resources
- ❌ Misleading "success" indicators

### After Fix (WORKING)
- ✅ Real LLM-generated summaries
- ✅ GPU monitoring and optimization
- ✅ Smart 7b→14b→nano routing
- ✅ Comprehensive metrics
- ✅ Robust retry logic
- ✅ Proper error handling
- ✅ Cost optimization through routing

---

## Priority Justification

**P0 - CRITICAL** because:
1. The daemon's primary purpose (enrichment) is completely non-functional
2. It silently produces garbage data that pollutes the RAG index
3. Users think it's working when it's not
4. Wastes significant system resources
5. Defeats the entire point of having a RAG daemon
6. Blocks any meaningful AI-assisted code search/analysis

This should be fixed **IMMEDIATELY** before any further daemon development.

---

## Files Affected

- `/home/vmlinux/src/llmc/tools/rag/service.py` (MODIFY)
- `/home/vmlinux/src/llmc/tools/rag/cli.py` (CONTEXT)
- `/home/vmlinux/src/llmc/tools/rag/workers.py` (CONTEXT)
- `/home/vmlinux/src/llmc/tools/rag/runner.py` (USE)
- `/home/vmlinux/src/llmc/scripts/qwen_enrich_batch.py` (REFERENCE)

---

**End of Investigation Report**
