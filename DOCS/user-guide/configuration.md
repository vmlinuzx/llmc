# Configuration Guide

LLMC uses **TOML** for configuration. It supports a cascading configuration model:
1.  **Global defaults**: Hardcoded in the application.
2.  **User Global**: `~/.llmc/config.toml` (Optional).
3.  **Repo Level**: `llmc.toml` in the root of your repository.

**Recommendation**: Always create an `llmc.toml` in your repo root.

---

## The `llmc.toml` Structure

A typical configuration file looks like this:

```toml
[rag]
# Exclude these patterns from indexing
ignore_patterns = ["tests/", "dist/", "*.min.js"]

# Embedding model to use
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"

[enrichment]
# Default provider for enrichment
default_provider = "ollama"
# Default model size/tier
default_tier = "7b"

[router]
# Route python files to the 'code' chain
"*.py" = "code"
# Route markdown to the 'docs' chain
"*.md" = "docs"

[chains.code]
provider = "ollama"
model = "qwen2.5-coder:7b"
prompt = "summarize_code"

[chains.docs]
provider = "ollama"
model = "mistral:7b"
prompt = "summarize_docs"
```

## Key Sections

### `[rag]`
Controls the indexing process.
- `ignore_patterns`: List of glob patterns to skip. Respects `.gitignore` by default, but this adds extra ignores (like tests or legacy code).
- `embedding_model`: The HuggingFace model ID for local embeddings.

### `[enrichment]`
Controls the LLM pipeline for generating metadata.
- `enforce_latin1_enrichment`: (bool) If true, drops non-latin characters to prevent vector database poisoning from binary garbage.
- `max_failures_per_span`: (int) Retries before giving up on enriching a difficult span.

### `[router]`
Maps file extensions or glob patterns to **Enrichment Chains**.
- Keys are patterns (`"*.py"`).
- Values are chain names (`"code"`).

### `[chains.*]`
Defines a specific processing pipeline.
- `provider`: `ollama`, `openai`, `anthropic`, `deepseek`.
- `model`: The specific model string (e.g., `gpt-4o`, `qwen2.5:14b`).
- `tier`: Logical size (`7b`, `70b`, `frontier`) used for fallback logic.

## Inheritance & Overrides

If you have a `~/.llmc/config.toml`, it applies to all repos. A repo-specific `llmc.toml` overrides conflicting keys.

For example, you might set a global `embedding_model`, but override `ignore_patterns` per repo.
