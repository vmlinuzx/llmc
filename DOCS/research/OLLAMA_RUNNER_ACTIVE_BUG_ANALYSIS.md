# Post-Mortem: The "runner_active" Hang in Qwen Enrichment

**Date:** 2025-11-23
**Status:** Confirmed Bug
**Severity:** Critical (Hangs Pipeline)
**Component:** `scripts/qwen_enrich_batch.py` (Legacy) and `tools/rag/llm_client.py` (Refactored)

---

## 1. The Symptom

When running `qwen_enrich_batch.py` (either manually or via `llmc-rag-service`), the process hangs indefinitely at the start of a batch, often after printing:

```text
[enrich] Starting batch for /path/to/repo (limit=50)
```

No CPU usage, no network traffic, just silence. The process is sleeping.

## 2. The Culprit Code

In `call_via_ollama`, the following logic exists to "wait for the runner to be ready":

```python
    def runner_active() -> bool:
        try:
            output = subprocess.check_output(["ollama", "ps"], text=True)
        except Exception:
            return False
        return model_name in output

    while runner_active():
        time.sleep(max(0.5, poll_wait))
```

## 3. The Logic Flaw

**Intent:**
The likely intent was: "Check if *another* process is currently running a generation with this model, and wait for it to finish so we don't overload the GPU."

**Reality:**
`ollama ps` lists **loaded models** in memory.

Example `ollama ps` output:
```text
NAME                       ID              SIZE      PROCESSOR    UNTIL
qwen2.5:7b-instruct-q4_K_M  8c3...          4.7 GB    100% GPU     5 minutes from now
```

If the model is **loaded** (which it is after the first call, or if `ollama run` was used recently), `model_name in output` returns **True**.

The loop `while runner_active(): sleep()` therefore translates to:

> **"Wait until the model is completely unloaded from VRAM."**

Since Ollama has a default `keep_alive` of 5 minutes (and our scripts often request 15m+), this script will sleep for 5-15 minutes *between every batch* (or at startup if the model was already warm).

If the script itself requests `keep_alive` (which it does), it effectively locks itself out:
1. It wants to run.
2. It sees the model is loaded.
3. It waits for it to unload.
4. (If parallel runners keep it loaded, it waits forever).

## 4. Why It Was "Mangling Along" Before

This bug might have been masked by:

1.  **Cold Starts:** If the model wasn't loaded when the script started, `runner_active()` returns False immediately, allowing the first call to proceed.
2.  **Fast Unloading:** If `keep_alive` was 0 or very short in previous configurations, the race condition might have been winnable.
3.  **Different Model Names:** If the script checked for `qwen2.5:7b` but `ollama ps` showed `qwen2.5:7b-instruct`, the string match might have failed (returning False), allowing execution to proceed (accidentally working).
4.  **Concurrency:** If multiple `qwen_enrich_batch` processes were running, they might have actually been serializing each other via this bug (one waits for the other to unload), making it *slow* but not strictly broken, until the keep-alive settings were tuned up.

## 5. The Fix

**Remove the loop.**

Ollama manages its own queue. If a request comes in while the model is busy, Ollama queues it. There is no need for the client to poll `ollama ps` and sleep.

### Corrected Logic

```python
    # Logic to wait for 'runner_active' removed as it blocks on loaded models.
    # Ollama handles concurrency internally.
    
    attempt = 0
    # ... proceed to generate request ...
```

## 6. Impact on Refactor

This bug was present in the legacy script and was **faithfully copied** into the new `tools/rag/llm_client.py` during the refactor, carrying the deadlock over.

Identifying and removing this loop fixes the hang in both the legacy script and the new pipeline.
