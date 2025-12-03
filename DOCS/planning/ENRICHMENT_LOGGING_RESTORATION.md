# Enrichment Logging Restoration

**Date**: 2025-12-03  
**Issue**: Gemini 3.0 fixed the service hanging bug but removed detailed per-span enrichment logs  
**Resolution**: Restored verbose logging while preserving the graceful shutdown fix

## Background

The `llmc-rag` service had a critical bug where it would hang during shutdown, requiring a 90-second timeout and SIGKILL. Gemini 3.0 fixed this by adding:
- `stop_check` callback to allow graceful interruption
- `progress_callback` for batch progress updates

However, in the process, the detailed **per-span enrichment logs** were lost. These logs provided line-level detail that was "really useful" for monitoring enrichment progress.

## Old Log Format (from qwen_enrich_batch.py)

The original enrichment logs showed:

```
Stored enrichment 42: tools/rag/database.py:156-189 (2.34s) via tier 7b (qwen2.5:7b) [chain=default, backend=ollama, url=http://localhost:11434]
```

**Details included:**
- ✅ **Span number** - Sequential enrichment count (e.g., "42")
- ✅ **File path and line range** - Exact location (e.g., `database.py:156-189`)
- ✅ **Duration** - How long it took (e.g., `2.34s`)
- ✅ **Tier** - Which model tier was used (e.g., `7b`, `14b`, `nano`)
- ✅ **Model name** - Specific model (e.g., `qwen2.5:7b`)
- ✅ **Chain name** - Enrichment chain from config
- ✅ **Backend** - Which backend (ollama, gateway, etc.)
- ✅ **Host/URL** - Where the model was running
- ✅ **Attempt count** - If retries were needed

## New Log Format (Restored)

The restored logs now show:

```
✓ Enriched span 42: tools/rag/database.py:156-189 (2.34s) (qwen2.5:7b) [chain=default, backend=ollama, url=http://localhost:11434]
```

For failures:
```
✗ Failed span 43: tools/rag/workers.py:200-250 (1.87s) [3 attempts] - BackendError: All backends exhausted
```

**Key differences from old format:**
- Added visual indicators: `✓` for success, `✗` for failure
- Slightly more compact format
- Attempt count shown when > 1
- Failure messages truncated to 100 chars for readability

## What Was Preserved

The graceful shutdown fix remains intact:
- ✅ `stop_check` callback still allows interruption
- ✅ `progress_callback` still provides batch-level updates
- ✅ Service shuts down cleanly in ~11s (not 90s timeout)

## Implementation Details

**Modified file**: `tools/rag/enrichment_pipeline.py`

**Changes**:
1. Updated `_process_span()` to accept `span_number` parameter
2. Added `_log_enrichment_success()` method with detailed logging
3. Added `_log_enrichment_failure()` method for error cases
4. Updated `process_batch()` to pass span number to `_process_span()`

**Log output locations**:
- Success logs → `stdout` (with `flush=True` for real-time visibility)
- Failure logs → `stderr` (with `flush=True`)

## Testing

To verify the restored logging:

```bash
# Start the RAG service
systemctl --user start llmc-rag

# Watch the logs in real-time
journalctl --user -u llmc-rag -f

# You should now see detailed per-span logs like:
# ✓ Enriched span 1: llmc/core.py:45-67 (1.23s) (qwen2.5:7b) [chain=default, backend=ollama]
# ✓ Enriched span 2: llmc/enrichment.py:100-145 (2.45s) (qwen2.5:7b) [chain=default, backend=ollama]
```

## References

- **AAR**: `DOCS/planning/AAR_2025-12-02_SERVICE_FIX.md` - Documents the original shutdown bug fix
- **Old implementation**: `scripts/qwen_enrich_batch.py` lines 2438-2441 - Original logging code
- **New implementation**: `tools/rag/enrichment_pipeline.py` lines 503-572 - Restored logging methods
