# Enrichment

<!-- TODO: Phase 3b will flesh this out -->

Enrichment uses LLMs to add AI-generated summaries, tags, and metadata to your indexed code spans.

---

## In This Section

- [Providers](providers.md) — Ollama, Gemini, Anthropic, OpenAI, Groq

---

## Quick Start

Enrichment runs automatically when the daemon is active:

```bash
# Start the enrichment daemon
llmc-cli service start

# Check enrichment status
llmc-cli stats
```

---

## See Also

- [Daemon Operations](../../operations/daemon.md)
- [Remote LLM Providers](providers.md)
