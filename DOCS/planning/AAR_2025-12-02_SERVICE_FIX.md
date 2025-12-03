# After Action Report: Service Shutdown & Enrichment Visibility Fix
Date: 2025-12-02
Author: Antigravity

## 1. Incident Summary
The `llmc-rag` service was exhibiting two issues:
1.  **Shutdown Timeout**: The service failed to stop gracefully, timing out after 90 seconds and being killed by `systemd`.
2.  **Perceived Inactivity**: The user reported "it's saying it's enriching, but it's just not", due to long periods of silence during batch processing.

## 2. Root Cause Analysis
### Shutdown Timeout
- The `EnrichmentPipeline.process_batch` method processed a batch of items (default 50) in a loop.
- This loop did not check for any exit signals or stop conditions.
- If a batch was in progress when `systemctl stop` was issued, the service would continue processing until the entire batch was done.
- With "chonky" (large/slow) items taking up to 120s each, a batch could take significantly longer than the systemd timeout.

### Perceived Inactivity
- `EnrichmentPipeline` only logged at the start and end of a batch.
- With a batch size of 50 and potential item duration of 120s, the service could be silent for extended periods (minutes to hours in worst case).
- This lack of feedback led the user to believe the service was hung.

## 3. Resolution
### Code Changes
1.  **`tools/rag/enrichment_pipeline.py`**:
    - Updated `process_batch` to accept a `stop_check` callback (returning `bool`) and a `progress_callback` (accepting `current`, `total`).
    - Added a check `if stop_check and stop_check(): break` inside the processing loop.
    - Added `progress_callback(i + 1, total_pending)` call inside the loop.

2.  **`tools/rag/service.py`**:
    - Updated `RAGService.process_repo` to pass `stop_check=lambda: not self.running`.
    - Implemented a `progress_cb` that logs "Processing... X/Y spans" every 5 items.
    - Passed this callback to `process_batch`.

### Verification
- **Shutdown**: `time systemctl --user stop llmc-rag` reduced from >90s (timeout) to ~11s (finishing current item).
- **Visibility**: Logs now show incremental progress (e.g., `... processed 5/50 spans`), confirming the service is active even during long batches.

## 4. Lessons Learned
- Long-running loops in services must always have an interruption mechanism.
- User visibility into batch processes is critical for UX, especially when individual items have high variance in processing time.
- `systemd` timeouts are a symptom, not the root cause; increasing the timeout would have masked the issue.
