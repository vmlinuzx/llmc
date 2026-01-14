# LiteLLM Backends

Unified backend layer for LLM providers using [LiteLLM](https://github.com/BerriAI/litellm).

## Overview

This package provides two backends that share common logic via `LiteLLMCore`:

| Backend | Interface | Use Case |
|---------|-----------|----------|
| `LiteLLMAgentBackend` | Async (`Backend` ABC) | llmc_agent chat/tool calling |
| `LiteLLMEnrichmentAdapter` | Sync (`BackendAdapter` Protocol) | RAG enrichment pipeline |

## Usage

### Enable LiteLLM in Config

Add to your `llmc.toml`:

```toml
[litellm]
enabled = true
model = "ollama_chat/qwen3-next-80b"  # LiteLLM format
# api_key = "sk-..."  # For cloud providers
# api_base = "http://localhost:8080"  # For custom endpoints
temperature = 0.7
max_tokens = 4096
timeout = 120.0
num_retries = 3
```

Or via environment variable:

```bash
LLMC_LITELLM_ENABLED=true bx "your question"
LLMC_LITELLM_MODEL=anthropic/claude-3-haiku bx "your question"
```

### Model Naming Convention

| Provider | LiteLLM Model Format | Example |
|----------|---------------------|---------|
| Ollama | `ollama_chat/model` | `ollama_chat/qwen3-next-80b` |
| OpenAI | `openai/model` | `openai/gpt-4o` |
| Anthropic | `anthropic/model` | `anthropic/claude-3-haiku-20240307` |
| Groq | `groq/model` | `groq/llama3-70b-8192` |
| Custom | `openai/model` + `api_base` | See below |

### Custom Endpoints (llama.cpp, vLLM, etc.)

```toml
[litellm]
enabled = true
model = "openai/local-model"
api_base = "http://localhost:8080/v1"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLMC Application                          │
├─────────────────────────────────────────────────────────────┤
│  llmc_agent (Chat)       │     llmc/rag (Enrichment)        │
│  Uses: Backend ABC       │     Uses: BackendAdapter Protocol│
│         (async)          │              (sync)              │
└────────────┬─────────────┴──────────────┬───────────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────────┐  ┌─────────────────────────────────┐
│  LiteLLMAgentBackend    │  │  LiteLLMEnrichmentAdapter       │
│  async generate()       │  │  sync generate()                │
│  async generate_stream()│  │  describe_host()                │
│  async generate_tools() │  │  config property                │
│  async health_check()   │  │                                 │
└───────────┬─────────────┘  └───────────────┬─────────────────┘
            │                                │
            └────────────┬───────────────────┘
                         ▼
            ┌─────────────────────────────────┐
            │       LiteLLMCore (shared)      │
            │  - Config handling              │
            │  - Model name translation       │
            │  - Response parsing             │
            │  - Exception mapping            │
            │  - Tool call normalization      │
            └─────────────────────────────────┘
                         │
                         ▼
            ┌─────────────────────────────────┐
            │  litellm.acompletion/completion │
            └─────────────────────────────────┘
```

## Design Reference

See: `DOCS/planning/HLD-litellm-migration-FINAL.md`
