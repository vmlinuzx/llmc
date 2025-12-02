# Implementation Plan: Remote LLM Provider Support

**Feature Branch:** `feature/remote-llm-providers`  
**Based on SDD:** `SDD_Remote_LLM_Providers.md`  
**Start Date:** 2025-12-02  
**Status:** 🟢 In Progress  

---

## Objectives

Enable LLMC's enrichment pipeline to use remote API providers (Gemini, OpenAI, Anthropic, Groq) with production-grade reliability patterns.

**Success Criteria:**
- ✅ Generic RemoteBackend adapter works
- ✅ At least Gemini and one other provider working
- ✅ Retry middleware with exponential backoff operational
- ✅ Rate limiting prevents API quota violations
- ✅ Cost tracking with budget caps functional
- ✅ All existing tests pass
- ✅ New integration tests for remote providers pass

---

## Implementation Phases

### Phase 1: Foundation & Reliability Middleware ✅
**Effort:** 4-5 hours  
**Status:** Complete

#### 1.1 Create reliability middleware module
- [x] Create `tools/rag/enrichment_reliability.py`
- [x] Implement `RetryMiddleware` with exponential backoff + jitter
- [x] Implement `RateLimiter` with token bucket algorithm
- [x] Implement `CircuitBreaker` for fail-fast behavior
- [x] Implement `CostTracker` for budget monitoring
- [x] Add unit tests for each middleware component

#### 1.2 Create provider registry and config
- [x] Create `tools/rag/enrichment_config.py`
- [x] Define `PROVIDERS` registry with defaults
- [x] Implement config loading from `llmc.toml`
- [x] Add environment variable resolution for API keys

---

### Phase 2: Base Remote Backend ✅
**Effort:** 3-4 hours  
**Status:** Complete

#### 2.1 Create base remote adapter
- [x] Create `tools/rag/enrichment_adapters/base.py`
- [x] Implement `RemoteBackend` base class
- [x] Add common HTTP client logic
- [x] Add authentication handling
- [x] Add timeout and error handling
- [x] Integrate reliability middleware hooks

---

### Phase 3: Gemini Provider ✅
**Effort:** 2-3 hours  
**Status:** Complete

#### 3.1 Gemini adapter implementation
- [x] Create `tools/rag/enrichment_adapters/gemini.py`
- [x] Implement `GeminiBackend` class
- [x] Add Gemini API client integration
- [x] Handle Gemini-specific request/response formats
- [x] Add error mapping for Gemini errors
- [ ] Test with live API (manual - needs API key)

---

### Phase 4: OpenAI-Compatible Providers ✅
**Effort:** 2-3 hours  
**Status:** Complete

#### 4.1 OpenAI adapter
- [x] Create `tools/rag/enrichment_adapters/openai_compat.py`
- [x] Implement `OpenAICompatBackend` class
- [x] Support OpenAI API
- [x] Support Groq API (OpenAI-compatible)
- [ ] Add streaming support (deferred - optional)
- [ ] Test with both OpenAI and Groq (manual - needs API keys)

---

### Phase 5: Anthropic Provider ✅
**Effort:** 2-3 hours  
**Status:** Complete

#### 5.1 Anthropic adapter
- [x] Create `tools/rag/enrichment_adapters/anthropic.py`
- [x] Implement `AnthropicBackend` class
- [x] Handle Anthropic-specific formats
- [ ] Test with Anthropic API (manual - needs API key)

---

### Phase 6: Configuration & Integration ✅
**Effort:** 2-3 hours  
**Status:** Complete

#### 6.1 Backend factory
- [x] Create `tools/rag/enrichment_factory.py`
- [x] Implement unified backend factory
- [x] Integrate middleware into backend creation
- [x] Add cost tracker factory

#### 6.2 Update pipeline integration
- [x] Update `enrichment_pipeline.py` documentation
- [x] Export factory from appropriate modules

---

### Phase 7: Testing ✅
**Effort:** 3-4 hours  
**Status:** Complete

#### 7.1 Unit tests
- [x] Test retry logic (backoff, jitter, max retries)
- [x] Test rate limiter (RPM, TPM)
- [x] Test circuit breaker (open, half-open, closed)
- [x] Test cost tracker (daily/monthly caps)
- [x] Test provider registry
- [x] Test backend factory

#### 7.2 Integration tests
- [ ] Create mock HTTP server for CI testing (deferred)
- [ ] Test cascade with remote failover (deferred)
- [ ] Test full pipeline with remote backend (deferred)
- [ ] Test error scenarios (429, 500, timeout) (deferred)

#### 7.3 Manual testing
- [ ] Test with real Gemini API (needs user API key)
- [ ] Test with real OpenAI API (needs user API key)
- [ ] Test with real Groq API (needs user API key)
- [ ] Verify cost tracking accuracy (needs real usage)

---

### Phase 8: Documentation & Polish ⏳
**Effort:** 2 hours  
**Status:** In Progress

#### 8.1 Documentation
- [ ] Update `README.md` with remote provider setup
- [ ] Update `tools/rag/USAGE.md` with examples
- [ ] Document environment variables
- [ ] Add troubleshooting guide

#### 8.2 Observability
- [ ] Add structured logging for remote calls
- [ ] Add metrics for retry/rate-limit/circuit events
- [ ] Add cost tracking output

---

## File Structure

```
tools/rag/
├── enrichment_backends.py           # Existing (unchanged)
├── enrichment_reliability.py        # NEW - middleware
├── enrichment_config.py             # NEW - provider registry
├── enrichment_adapters/
│   ├── __init__.py                  # Update exports
│   ├── ollama.py                    # Existing
│   ├── base.py                      # NEW - RemoteBackend base
│   ├── gemini.py                    # NEW - Gemini
│   ├── openai_compat.py             # NEW - OpenAI + Groq
│   └── anthropic.py                 # NEW - Anthropic
└── tests/
    └── test_remote_backends.py      # NEW - comprehensive tests
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API quota exhaustion during testing | Use mock servers in CI, add hard limits |
| Cost overruns | Implement strict budget caps, fail-safe defaults |
| Breaking existing Ollama workflows | Zero changes to existing code paths |
| Provider API changes | Version-lock dependencies, add CI alerts |
| Rate limit edge cases | Comprehensive token bucket testing |

---

## Dependencies

**New Python packages needed:**
```bash
pip install google-generativeai  # Gemini
pip install openai              # OpenAI, Groq (OpenAI-compatible)
pip install anthropic           # Anthropic
```

**Environment Variables:**
- `GOOGLE_API_KEY` - Gemini
- `OPENAI_API_KEY` - OpenAI
- `ANTHROPIC_API_KEY` - Anthropic
- `GROQ_API_KEY` - Groq

---

## Rollout Plan

1. **Local Testing** - Develop and test with mock servers
2. **Dev Environment** - Test with real APIs using test keys
3. **Controlled Rollout** - Enable one provider at a time
4. **Monitor** - Watch costs and error rates
5. **Documentation** - Update all docs before merge
6. **Merge** - PR review and merge to main

---

## Exit Criteria

- [ ] All phase tasks completed
- [ ] All existing tests passing
- [ ] New tests added and passing
- [ ] Documentation updated
- [ ] Manual testing with ≥2 remote providers successful
- [ ] Cost tracking verified accurate
- [ ] No regression in existing Ollama functionality
- [ ] Code reviewed and approved

---

## Notes

- Prioritize stability over features
- Keep Ollama path completely unchanged
- Add extensive logging for debugging
- Fail gracefully with clear error messages
- Document all API-specific quirks
