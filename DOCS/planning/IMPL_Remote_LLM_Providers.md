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

### Phase 1: Foundation & Reliability Middleware ⏳
**Effort:** 4-5 hours  
**Status:** Starting

#### 1.1 Create reliability middleware module
- [ ] Create `tools/rag/enrichment_reliability.py`
- [ ] Implement `RetryMiddleware` with exponential backoff + jitter
- [ ] Implement `RateLimiter` with token bucket algorithm
- [ ] Implement `CircuitBreaker` for fail-fast behavior
- [ ] Implement `CostTracker` for budget monitoring
- [ ] Add unit tests for each middleware component

#### 1.2 Create provider registry and config
- [ ] Create `tools/rag/enrichment_config.py`
- [ ] Define `PROVIDERS` registry with defaults
- [ ] Implement config loading from `llmc.toml`
- [ ] Add environment variable resolution for API keys

---

### Phase 2: Base Remote Backend ⏳
**Effort:** 3-4 hours  
**Status:** Pending

#### 2.1 Create base remote adapter
- [ ] Create `tools/rag/enrichment_adapters/base.py`
- [ ] Implement `RemoteBackend` base class
- [ ] Add common HTTP client logic
- [ ] Add authentication handling
- [ ] Add timeout and error handling
- [ ] Integrate reliability middleware hooks

---

### Phase 3: Gemini Provider ⏳
**Effort:** 2-3 hours  
**Status:** Pending

#### 3.1 Gemini adapter implementation
- [ ] Create `tools/rag/enrichment_adapters/gemini.py`
- [ ] Implement `GeminiBackend` class
- [ ] Add Gemini API client integration
- [ ] Handle Gemini-specific request/response formats
- [ ] Add error mapping for Gemini errors
- [ ] Test with live API (manual)

---

### Phase 4: OpenAI-Compatible Providers ⏳
**Effort:** 2-3 hours  
**Status:** Pending

#### 4.1 OpenAI adapter
- [ ] Create `tools/rag/enrichment_adapters/openai_compat.py`
- [ ] Implement `OpenAIBackend` class
- [ ] Support OpenAI API
- [ ] Support Groq API (OpenAI-compatible)
- [ ] Add streaming support (optional)
- [ ] Test with both OpenAI and Groq

---

### Phase 5: Anthropic Provider ⏳
**Effort:** 2-3 hours  
**Status:** Pending

#### 5.1 Anthropic adapter
- [ ] Create `tools/rag/enrichment_adapters/anthropic.py`
- [ ] Implement `AnthropicBackend` class
- [ ] Handle Anthropic-specific formats
- [ ] Test with Anthropic API

---

### Phase 6: Configuration & Integration ⏳
**Effort:** 2-3 hours  
**Status:** Pending

#### 6.1 Update llmc.toml schema
- [ ] Document new `[enrichment.providers.*]` sections
- [ ] Document pricing configuration
- [ ] Document cost caps
- [ ] Add example configs

#### 6.2 Update backend cascade initialization
- [ ] Modify backend factory to support remote providers
- [ ] Integrate middleware into cascade
- [ ] Add debug logging

---

### Phase 7: Testing ⏳
**Effort:** 3-4 hours  
**Status:** Pending

#### 7.1 Unit tests
- [ ] Test retry logic (backoff, jitter, max retries)
- [ ] Test rate limiter (RPM, TPM)
- [ ] Test circuit breaker (open, half-open, closed)
- [ ] Test cost tracker (daily/monthly caps)

#### 7.2 Integration tests
- [ ] Create mock HTTP server for CI testing
- [ ] Test cascade with remote failover
- [ ] Test full pipeline with remote backend
- [ ] Test error scenarios (429, 500, timeout)

#### 7.3 Manual testing
- [ ] Test with real Gemini API
- [ ] Test with real OpenAI API
- [ ] Test with real Groq API
- [ ] Verify cost tracking accuracy

---

### Phase 8: Documentation & Polish ⏳
**Effort:** 2 hours  
**Status:** Pending

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
