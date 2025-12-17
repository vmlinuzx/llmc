# Remote LLM Providers - Usage Guide

This guide shows how to configure and use remote LLM API providers (Gemini, OpenAI, Anthropic, Groq) in LLMC's enrichment pipeline.

## Quick Start

### 1. Install Dependencies

```bash
# If not already installed
pip install httpx
```

### 2. Set API Keys

```bash
export GOOGLE_API_KEY="your-gemini-api-key"      # For Gemini
export OPENAI_API_KEY="your-openai-api-key"      # For OpenAI
export ANTHROPIC_API_KEY="your-anthropic-key"    # For Anthropic
export GROQ_API_KEY="your-groq-api-key"          # For Groq
```

### 3. Configure llmc.toml

Add remote providers to your enrichment chain:

```toml
[enrichment]
default_chain = "tiered"
daily_cost_cap_usd = 5.00      # Optional: daily spending limit
monthly_cost_cap_usd = 50.00   # Optional: monthly spending limit

# Tier 1: Local Ollama (free, fast)
[[enrichment.chain]]
name = "local-7b"
chain = "tiered"
provider = "ollama"
model = "qwen2.5:7b-instruct"
url = "http://localhost:11434"
timeout_seconds = 120
enabled = true

# Tier 2: Gemini Flash (cheap, fast cloud fallback)
[[enrichment.chain]]
name = "gemini-flash"
chain = "tiered"
provider = "gemini"
model = "gemini-1.5-flash"
timeout_seconds = 30
enabled = true
retry_max = 3

# Tier 3: Claude Haiku (quality fallback)
[[enrichment.chain]]
name = "claude-haiku"
chain = "tiered"
provider = "anthropic"
model = "claude-3-haiku-20240307"
timeout_seconds = 30
enabled = false  # Enable when needed

# Optional: Override provider defaults
[enrichment.providers.gemini]
rpm_limit = 60
tpm_limit = 1000000

# Optional: Custom pricing
[enrichment.pricing.gemini]
input = 0.075   # Per 1M input tokens
output = 0.30   # Per 1M output tokens
```

### 4. Run Enrichment

```python
from llmc.rag.enrichment_pipeline import EnrichmentPipeline
from llmc.rag.enrichment_factory import create_backend_from_spec

pipeline = EnrichmentPipeline(
    db=database,
    router=enrichment_router,
    backend_factory=create_backend_from_spec,  # Uses new factory
    prompt_builder=build_enrichment_prompt,
)

result = pipeline.process_batch(limit=50)
print(f"Enriched {result.succeeded}/{result.attempted} spans")
```

---

## Supported Providers

### Gemini (Google)

**Models:**
- `gemini-1.5-flash` - Fast, cheap
- `gemini-1.5-pro` - Higher quality

**Configuration:**
```toml
[[enrichment.chain]]
name = "gemini"
provider = "gemini"
model = "gemini-1.5-flash"
timeout_seconds = 30
enabled = true
```

**API Key:** Set `GOOGLE_API_KEY` environment variable

**Pricing (approximate):**
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

---

### OpenAI

**Models:**
- `gpt-4o-mini` - Fast, cheap
- `gpt-4o` - High quality
- `gpt-3.5-turbo` - Legacy, cheap

**Configuration:**
```toml
[[enrichment.chain]]
name = "openai"
provider = "openai"
model = "gpt-4o-mini"
url = "https://api.openai.com/v1"  # Optional, this is the default
timeout_seconds = 30
enabled = true
```

**API Key:** Set `OPENAI_API_KEY` environment variable

**Pricing (gpt-4o-mini):**
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens

---

### Anthropic (Claude)

**Models:**
- `claude-3-haiku-20240307` - Fast, cheap
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-opus-20240229` - Highest quality

**Configuration:**
```toml
[[enrichment.chain]]
name = "claude"
provider = "anthropic"
model = "claude-3-haiku-20240307"
timeout_seconds = 30
enabled = true
```

**API Key:** Set `ANTHROPIC_API_KEY` environment variable

**Pricing (Haiku):**
- Input: $0.25 per 1M tokens
- Output: $1.25 per 1M tokens

---

### Groq

**Models:**
- `llama3-70b-8192` - Very fast, free tier available
- `llama3-8b-8192` - Even faster
- `mixtral-8x7b-32768` - Long context

**Configuration:**
```toml
[[enrichment.chain]]
name = "groq"
provider = "groq"
model = "llama3-70b-8192"
url = "https://api.groq.com/openai/v1"  # Optional
timeout_seconds = 30
enabled = true
```

**API Key:** Set `GROQ_API_KEY` environment variable

**Pricing:**
- Free tier available with rate limits
- Paid: ~$0.05-0.08 per 1M tokens

---

## Advanced Features

### Cost Tracking

Set budget caps to prevent runaway costs:

```toml
[enrichment]
daily_cost_cap_usd = 5.00
monthly_cost_cap_usd = 50.00
```

The pipeline will stop enriching when budgets are exceeded.

Check spending:
```python
from llmc.rag.enrichment_factory import create_cost_tracker_from_config

cost_tracker = create_cost_tracker_from_config(enrichment_config)
print(f"Daily spend: ${cost_tracker.daily_spend:.4f}")
print(f"Monthly spend: ${cost_tracker.monthly_spend:.4f}")
```

---

### Rate Limiting

Providers have different rate limits. Override defaults:

```toml
[enrichment.providers.gemini]
rpm_limit = 60        # Requests per minute
tpm_limit = 1000000   # Tokens per minute
```

The rate limiter will automatically throttle requests to stay within limits.

---

### Circuit Breaker

After 5 consecutive failures, the circuit breaker opens for 60 seconds:

- **Closed**: Normal operation
- **Open**: Fast-fail without attempting requests
- **Half-Open**: Testing if service recovered

This prevents wasting time on dead endpoints.

---

### Retry Logic

Failed requests are automatically retried with exponential backoff:

```toml
[[enrichment.chain]]
name = "gemini"
provider = "gemini"
model = "gemini-1.5-flash"
retry_max = 3                # Retry up to 3 times
retry_backoff_base = 1.0     # Base delay: 1s, 2s, 4s...
```

Retryable errors:
- `429 Too Many Requests` - Rate limit hit
- `500/502/503/504` - Server errors
- Timeouts

Non-retryable errors:
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Bad API key
- `403 Forbidden` - Billing/quota issue
- `404 Not Found` - Bad model name

---

## Migration from Ollama-Only

If you're currently using only Ollama, no changes needed! The new system is fully backward compatible:

```python
# Old way (still works)
from llmc.rag.enrichment_adapters.ollama import OllamaBackend
backend_factory = OllamaBackend.from_spec

# New way (supports all providers)
from llmc.rag.enrichment_factory import create_backend_from_spec
backend_factory = create_backend_from_spec
```

---

## Tiered Failover Strategy

Configure a tiered cascade for maximum reliability:

```toml
# Tier 1: Free local (first choice)
[[enrichment.chain]]
name = "local-7b"
chain = "tiered"
provider = "ollama"
model = "qwen2.5:7b"
url = "http://localhost:11434"
enabled = true

# Tier 2: Fast cloud (if local fails)
[[enrichment.chain]]
name = "gemini-flash"
chain = "tiered"
provider = "gemini"
model = "gemini-1.5-flash"
enabled = true

# Tier 3: Premium quality (last resort)
[[enrichment.chain]]
name = "claude-haiku"
chain = "tiered"
provider = "anthropic"
model = "claude-3-haiku-20240307"
enabled = false  # Manual override only
```

This configuration:
1. Tries local Ollama first (free, fast)
2. Falls back to Gemini if local fails (cheap cloud)
3. Can manually enable Claude for critical work (premium)

---

## Troubleshooting

### "Budget exceeded" error

Your daily or monthly cap was reached. Options:
1. Increase cap in `llmc.toml`
2. Wait for daily/monthly reset
3. Use local Ollama instead

### "Circuit breaker is open" error

Too many consecutive failures. The breaker will auto-recover after 60 seconds.

### "API key not found" error

Make sure environment variables are set:
```bash
export GOOGLE_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
```

### "Rate limit exceeded" error

You're hitting API rate limits. The system automatically throttles, but you can:
1. Reduce batch size
2. Add delay between requests
3. Upgrade API tier with provider

---

## Best Practices

1. **Start with cheap tiers**: Use local → Gemini → premium cascade
2. **Set budget caps**: Prevent surprise bills
3. **Monitor costs**: Check spending regularly
4. **Test with small batches**: Verify config before large runs
5. **Use local for development**: Save API quota for production

---

## Example Configurations

### Development (Local Only)
```toml
[[enrichment.chain]]
name = "local"
chain = "default"
provider = "ollama"
model = "qwen2.5:7b"
url = "http://localhost:11434"
enabled = true
```

### Production (Tiered Reliability)
```toml
[enrichment]
daily_cost_cap_usd = 10.00

[[enrichment.chain]]
name = "local"
chain = "prod"
provider = "ollama"
model = "qwen2.5:14b"
url = "http://gpu-server:11434"
enabled = true

[[enrichment.chain]]
name = "cloud-fallback"
chain = "prod"
provider = "gemini"
model = "gemini-1.5-flash"
enabled = true
```

### Cost-Conscious (Free Tier)
```toml
[[enrichment.chain]]
name = "groq-fast"
chain = "free"
provider = "groq"
model = "llama3-70b-8192"
enabled = true
retry_max = 5  # Groq free tier can be flaky

[[enrichment.chain]]
name = "local-backup"
chain = "free"
provider = "ollama"
model = "qwen2.5:7b"
url = "http://localhost:11434"
enabled = true
```

---

## API Resources

- **Gemini**: https://ai.google.dev/pricing
- **OpenAI**: https://platform.openai.com/docs/api-reference
- **Anthropic**: https://docs.anthropic.com/claude/reference
- **Groq**: https://console.groq.com/docs
