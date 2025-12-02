# SDD: Remote LLM Provider Support for Enrichment

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Design Complete  

---

## Executive Summary

LLMC's enrichment pipeline uses a simple failover cascade - if backend A fails, try backend B. Currently only Ollama (local) works. This SDD adds support for remote API providers (Gemini, OpenAI, Anthropic, Groq) with the reliability patterns required for production API usage.

**Goal:** Make `provider = "gemini"` (etc.) actually work in `[[enrichment.chain]]` configs.

---

## 1. Current State

### What Works
```toml
[[enrichment.chain]]
name = "athena"
provider = "ollama"        # ✅ Works
model = "qwen2.5:7b"
url = "http://192.168.5.20:11434"

[[enrichment.chain]]
name = "athena-14b"
provider = "ollama"        # ✅ Works (failover)
model = "qwen2.5:14b"
url = "http://192.168.5.20:11434"
```

### What Doesn't Work
```toml
[[enrichment.chain]]
name = "gemini-flash"
provider = "gemini"        # ❌ No adapter exists
model = "gemini-1.5-flash"

[[enrichment.chain]]
name = "groq-70b"
provider = "groq"          # ❌ No adapter exists
model = "llama3-70b-8192"
```

### The Gap
- `tools/rag/enrichment_backends.py` has `BackendAdapter` protocol
- Only `OllamaBackend` implements it
- No adapters for: Gemini, OpenAI, Anthropic, Groq, Azure, etc.
- No reliability patterns (backoff, rate limits, circuit breaker)

---

## 2. Design

### 2.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BackendCascade                          │
│                                                             │
│   ┌──────────────┐                                          │
│   │ OllamaBackend│  (existing)                              │
│   └──────┬───────┘                                          │
│          │ fail                                             │
│          ▼                                                  │
│   ┌──────────────┐    ┌─────────────────┐                   │
│   │ RemoteBackend│───▶│ RetryMiddleware │                   │
│   │   (Gemini)   │    │  - Backoff      │                   │
│   └──────┬───────┘    │  - Rate limits  │                   │
│          │ fail       │  - Circuit break│                   │
│          ▼            └─────────────────┘                   │
│   ┌──────────────┐                                          │
│   │ RemoteBackend│                                          │
│   │   (OpenAI)   │                                          │
│   └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 New Components

| Component | Responsibility |
|-----------|----------------|
| `RemoteBackend` | Generic adapter for HTTP/REST LLM APIs |
| `ProviderConfig` | Provider-specific settings (endpoints, auth, headers) |
| `RetryMiddleware` | Exponential backoff, jitter, max retries |
| `RateLimiter` | Token bucket per provider, respects API limits |
| `CircuitBreaker` | Fail-fast after N consecutive failures |
| `CostTracker` | Running tally of API spend, optional hard cap |

### 2.3 Provider Registry

```python
PROVIDERS = {
    "ollama": {
        "adapter": "ollama",  # existing
        "auth": None,
        "base_url": "from config",
    },
    "gemini": {
        "adapter": "google-genai",
        "auth": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "rate_limit": {"rpm": 60, "tpm": 1_000_000},
    },
    "openai": {
        "adapter": "openai",
        "auth": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "rate_limit": {"rpm": 500, "tpm": 90_000},
    },
    "anthropic": {
        "adapter": "anthropic",
        "auth": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "rate_limit": {"rpm": 50, "tpm": 100_000},
    },
    "groq": {
        "adapter": "openai",  # OpenAI-compatible
        "auth": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "rate_limit": {"rpm": 30, "tpm": 6_000},
    },
    "azure": {
        "adapter": "azure-openai",
        "auth": "AZURE_OPENAI_API_KEY",
        "base_url": "from config",  # deployment-specific
        "rate_limit": {"rpm": 60, "tpm": 90_000},
    },
}
```

---

## 3. Reliability Patterns

### 3.1 Exponential Backoff with Jitter

```python
def backoff_delay(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate delay with exponential backoff + jitter."""
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter

# Retry sequence: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped)
```

### 3.2 Rate Limiter (Token Bucket)

```python
@dataclass
class RateLimiter:
    """Per-provider rate limiting."""
    
    requests_per_minute: int
    tokens_per_minute: int
    _request_times: deque = field(default_factory=deque)
    _token_count: int = 0
    _token_window_start: float = 0
    
    def acquire(self, estimated_tokens: int = 1000) -> float:
        """
        Returns delay in seconds before request can proceed.
        Returns 0 if request can proceed immediately.
        """
        now = time.monotonic()
        
        # Check RPM
        self._prune_old_requests(now)
        if len(self._request_times) >= self.requests_per_minute:
            oldest = self._request_times[0]
            rpm_wait = 60 - (now - oldest)
        else:
            rpm_wait = 0
        
        # Check TPM
        if now - self._token_window_start > 60:
            self._token_count = 0
            self._token_window_start = now
        
        if self._token_count + estimated_tokens > self.tokens_per_minute:
            tpm_wait = 60 - (now - self._token_window_start)
        else:
            tpm_wait = 0
        
        return max(rpm_wait, tpm_wait)
    
    def record(self, actual_tokens: int):
        """Record a completed request."""
        self._request_times.append(time.monotonic())
        self._token_count += actual_tokens
```

### 3.3 Circuit Breaker

```python
@dataclass
class CircuitBreaker:
    """Fail-fast after repeated failures."""
    
    failure_threshold: int = 5      # Open after N consecutive failures
    recovery_timeout: float = 60.0  # Try again after N seconds
    
    _failure_count: int = 0
    _last_failure_time: float = 0
    _state: str = "closed"  # closed, open, half-open
    
    def can_proceed(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
                return True
            return False
        # half-open: allow one request through
        return True
    
    def record_success(self):
        self._failure_count = 0
        self._state = "closed"
    
    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
```

### 3.4 Cost Tracking

```python
@dataclass
class CostTracker:
    """Track API spend with optional hard cap."""
    
    # Pricing per 1M tokens (configurable in llmc.toml)
    pricing: dict[str, dict[str, float]]  # provider -> {input, output}
    
    daily_cap_usd: float | None = None
    monthly_cap_usd: float | None = None
    
    _daily_spend: float = 0
    _monthly_spend: float = 0
    _day_start: date = field(default_factory=date.today)
    
    def check_budget(self, provider: str, estimated_tokens: int) -> bool:
        """Returns True if request is within budget."""
        self._maybe_reset()
        
        price = self.pricing.get(provider, {})
        est_cost = (estimated_tokens / 1_000_000) * price.get("input", 0)
        
        if self.daily_cap_usd and self._daily_spend + est_cost > self.daily_cap_usd:
            return False
        if self.monthly_cap_usd and self._monthly_spend + est_cost > self.monthly_cap_usd:
            return False
        return True
    
    def record(self, provider: str, input_tokens: int, output_tokens: int):
        """Record actual spend."""
        price = self.pricing.get(provider, {})
        cost = (
            (input_tokens / 1_000_000) * price.get("input", 0) +
            (output_tokens / 1_000_000) * price.get("output", 0)
        )
        self._daily_spend += cost
        self._monthly_spend += cost
```

---

## 4. Configuration

### 4.1 llmc.toml Additions

```toml
[enrichment]
default_chain = "tiered"
daily_cost_cap_usd = 5.00      # Stop enrichment if daily spend exceeds
monthly_cost_cap_usd = 50.00   # Stop enrichment if monthly spend exceeds

# Tier 1: Local (free, fast, good enough for most)
[[enrichment.chain]]
name = "local-7b"
chain = "tiered"
provider = "ollama"
model = "qwen2.5:7b-instruct"
url = "http://192.168.5.20:11434"
timeout_seconds = 120
enabled = true

# Tier 2: Local larger (free, slower, better quality)
[[enrichment.chain]]
name = "local-14b"
chain = "tiered"
provider = "ollama"
model = "qwen2.5:14b-instruct-q4_K_M"
url = "http://192.168.5.20:11434"
timeout_seconds = 180
enabled = true

# Tier 3: Remote cheap (Gemini Flash - $0.075/1M input)
[[enrichment.chain]]
name = "gemini-flash"
chain = "tiered"
provider = "gemini"
model = "gemini-1.5-flash"
timeout_seconds = 30
enabled = true
retry_max = 3
retry_backoff_base = 1.0

# Tier 4: Remote quality (Claude Haiku - $0.25/1M input)
[[enrichment.chain]]
name = "claude-haiku"
chain = "tiered"
provider = "anthropic"
model = "claude-3-haiku-20240307"
timeout_seconds = 30
enabled = false  # Enable when you want to spend money

# Provider-specific settings
[enrichment.providers.gemini]
api_key_env = "GOOGLE_API_KEY"  # Or api_key = "..." directly
rpm_limit = 60
tpm_limit = 1000000

[enrichment.providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"
rpm_limit = 50
tpm_limit = 100000

[enrichment.providers.openai]
api_key_env = "OPENAI_API_KEY"
rpm_limit = 500
tpm_limit = 90000

# Pricing for cost tracking (per 1M tokens)
[enrichment.pricing.gemini]
input = 0.075
output = 0.30

[enrichment.pricing.anthropic]
input = 0.25
output = 1.25

[enrichment.pricing.openai]
input = 0.15
output = 0.60
```

### 4.2 Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GROQ_API_KEY` | Groq API key |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `LLMC_ENRICHMENT_COST_CAP` | Override daily cost cap |

---

## 5. Implementation Plan

| Phase | Effort | Difficulty | Deliverables |
|-------|--------|------------|--------------|
| **Phase 1: RemoteBackend base** | 3-4h | 🟡 Medium | Generic HTTP adapter with auth |
| **Phase 2: Gemini adapter** | 2-3h | 🟢 Easy | First working remote provider |
| **Phase 3: Retry middleware** | 2-3h | 🟢 Easy | Backoff, jitter, max retries |
| **Phase 4: Rate limiter** | 2-3h | 🟡 Medium | Token bucket per provider |
| **Phase 5: Circuit breaker** | 1-2h | 🟢 Easy | Fail-fast on repeated failures |
| **Phase 6: Cost tracking** | 2-3h | 🟢 Easy | Spend tracking, caps, alerts |
| **Phase 7: More providers** | 3-4h | 🟢 Easy | OpenAI, Anthropic, Groq, Azure |
| **Phase 8: Testing** | 2-3h | 🟡 Medium | Unit + integration tests |

**Total: 17-25 hours** (~3-4 focused sessions)

---

## 6. File Structure

```
tools/rag/
├── enrichment_backends.py      # Existing (add imports)
├── enrichment_adapters/        # NEW
│   ├── __init__.py
│   ├── base.py                 # RemoteBackend base class
│   ├── ollama.py               # Move existing Ollama code here
│   ├── gemini.py               # Google Gemini adapter
│   ├── openai_compat.py        # OpenAI + compatible (Groq)
│   ├── anthropic.py            # Anthropic adapter
│   └── azure.py                # Azure OpenAI adapter
├── enrichment_reliability.py   # NEW - middleware classes
│   ├── RetryMiddleware
│   ├── RateLimiter
│   ├── CircuitBreaker
│   └── CostTracker
└── enrichment_config.py        # NEW - provider registry + config loading
```

---

## 7. Error Handling

### Retryable Errors
- `429 Too Many Requests` → Backoff + wait for rate limit reset
- `500/502/503/504` → Backoff + retry
- `Connection timeout` → Backoff + retry
- `SSL errors` → Retry once, then fail

### Non-Retryable Errors
- `400 Bad Request` → Log + skip span (bad prompt?)
- `401 Unauthorized` → Fail chain (bad API key)
- `403 Forbidden` → Fail chain (quota/billing issue)
- `404 Not Found` → Fail chain (bad model name)

### Cascade Behavior
```
Span "foo.py:123"
    │
    ├─▶ ollama-7b: timeout (60s)
    │       └─▶ RETRY 1: timeout
    │           └─▶ CASCADE to next
    │
    ├─▶ ollama-14b: success! ✓
    │
    └─▶ (stop, don't try remote)
```

If local succeeds, remote is never called. Remote is true failover.

---

## 8. Observability

### Metrics to Track
- `enrichment_attempts_total{provider, model, status}`
- `enrichment_duration_seconds{provider, model}`
- `enrichment_retries_total{provider, reason}`
- `enrichment_circuit_breaker_state{provider}`
- `enrichment_cost_usd{provider, model}`
- `enrichment_rate_limit_waits_total{provider}`

### Log Events
```
INFO  Enriching span abc123 with ollama/qwen2.5:7b
WARN  ollama/qwen2.5:7b timeout, retrying (1/3)
WARN  ollama/qwen2.5:7b failed after 3 retries, cascading to gemini
INFO  Enriching span abc123 with gemini/gemini-1.5-flash
INFO  Enriched span abc123 in 1.2s (gemini, $0.0001)
```

---

## 9. Testing Strategy

### Unit Tests
- `test_backoff_delay()` - verify exponential + jitter
- `test_rate_limiter_rpm()` - verify request throttling
- `test_rate_limiter_tpm()` - verify token throttling
- `test_circuit_breaker_opens()` - verify fail-fast
- `test_circuit_breaker_recovers()` - verify half-open state
- `test_cost_tracker_caps()` - verify budget enforcement

### Integration Tests
- `test_gemini_adapter_live()` - real API call (skip in CI)
- `test_cascade_local_to_remote()` - mock local failure → remote
- `test_full_chain_with_reliability()` - end-to-end with all middleware

### Mock Server
For CI, use a mock HTTP server that simulates:
- Rate limit responses (429)
- Intermittent failures (500)
- Slow responses (for timeout testing)

---

## 10. Migration Path

### For Existing Users
1. No changes required - existing `ollama` configs work
2. To add remote: add `[[enrichment.chain]]` blocks with new providers
3. Set API keys via env vars
4. Optionally set cost caps

### Breaking Changes
None. This is purely additive.

---

## 11. Open Questions

1. **Persistent cost tracking?** Should spend be tracked in SQLite across restarts, or just in-memory per session?

2. **Provider-specific prompts?** Some providers work better with slightly different prompt formats. Support per-provider prompt templates?

3. **Streaming?** Some APIs support streaming responses. Worth implementing for faster perceived latency, or overkill for enrichment?

---

## Appendix A: API Quick Reference

### Gemini
```python
import google.generativeai as genai
genai.configure(api_key=key)
model = genai.GenerativeModel('gemini-1.5-flash')
response = model.generate_content(prompt)
```

### OpenAI / Groq (compatible)
```python
from openai import OpenAI
client = OpenAI(api_key=key, base_url=url)
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}]
)
```

### Anthropic
```python
import anthropic
client = anthropic.Anthropic(api_key=key)
response = client.messages.create(
    model=model,
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
```
