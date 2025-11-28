# RAG Enrichment Hardening Guide

This guide explains how LLMC's enrichment pipeline is designed to be resilient, how to configure it for reliability, and how to troubleshoot when things go wrong.

## Core Concepts

Enrichment is the process of adding semantic metadata (summaries, key topics, complexity scores) to code spans. This process relies on external LLM backends (Ollama, Gemini, etc.), which are inherently unreliable (network flakes, rate limits, model crashes).

To handle this, LLMC uses a **Backend Cascade** pattern:
1.  **Chains**: You define ordered lists of backends called "chains".
2.  **Fallbacks**: If the first backend in a chain fails, the system automatically tries the next one.
3.  **Retries**: The system can retry failed spans at the pipeline level.

## Configuration (`llmc.toml`)

All hardening settings are configured in the `[enrichment]` table of your `llmc.toml`.

### Global Settings

```toml
[enrichment]
# The default chain to use if none is specified
default_chain = "athena" 

# How many spans to process in one go
batch_size = 50 

# Stop retrying a specific span after this many total failures across all backends
max_failures_per_span = 4 

# Strict character encoding check (see below)
enforce_latin1_enrichment = true
```

### defining Chains

Use `[[enrichment.chain]]` blocks to define your backends. The order matters! LLMC tries them from top to bottom for a given chain name.

```toml
# Primary Backend: Fast, local model
[[enrichment.chain]]
name = "local-7b"
chain = "athena"          # Belongs to the "athena" chain
provider = "ollama"
model = "qwen2.5:7b"
url = "http://localhost:11434"
timeout_seconds = 120     # Fail fast if it hangs
enabled = true

# Fallback Backend: Slower, larger model (or remote API)
[[enrichment.chain]]
name = "local-14b"
chain = "athena"          # Also "athena", tried if local-7b fails
provider = "ollama"
model = "qwen2.5:14b"
url = "http://localhost:11434"
timeout_seconds = 180     # Give it more time
enabled = true
```

## `enforce_latin1_enrichment`

**What is it?**
When set to `true`, LLMC validates that the output from the LLM is valid Latin-1 (ISO-8859-1) text. If the model returns characters outside this range (e.g., complex emojis, obscure Unicode math symbols), the enrichment is considered a **failure** and the next backend is tried.

**Why use it?**
1.  **Database Compatibility**: Some older or embedded SQLite builds can have issues indexing complex Unicode for Full Text Search (FTS).
2.  **Hallucination Guard**: Small models often "glitch" and output garbage Unicode when they are confused. Forcing Latin-1 is a cheap heuristic to catch these hallucinations.
3.  **Token Efficiency**: It encourages the model to stick to plain English/Code descriptions.

**When to disable it?**
Set it to `false` if you are documenting code with non-Latin comments (Chinese, Japanese, etc.) or if your project uses emojis heavily in documentation.

## Troubleshooting & Triage

### 1. "Enrichment is stuck / 0% progress"
*   **Check connections**: Can you `curl` your Ollama instance?
*   **Check `batch_size`**: If set too high (e.g., 100+) on a small GPU, the model might be timing out processing the batch prompt. Lower it to 10 or 5.
*   **Check logs**: Look for `ReadTimeout` or `ConnectionRefusedError`.

### 2. "My database is full of partial enrichments"
*   This usually means the process was killed mid-batch.
*   **Fix**: Run `llmc-rag-daemon` (or the enrichment script) again. The system is idempotent and will pick up where it left off, re-processing incomplete spans.

### 3. "Backend Flapping" (Success then Failure)
*   **Thermal Throttling**: Your local GPU might be overheating and slowing down, causing timeouts. Increase `timeout_seconds` in `llmc.toml`.
*   **Context Window**: If specific files fail consistently, they might be too large for the model's context window. LLMC tries to chunk, but massive functions can still be an issue.

### 4. "Garbage / Repetitive Summaries"
*   **Check `temperature`**: In `options`, ensure `temperature` is low (0.1 or 0.2). High temperature makes models creative but unreliable for summarization.
    ```toml
    options = { num_ctx = 8192, temperature = 0.2 }
    ```
