# Local-First LLM Orchestration Notes

- **Source:** `/home/vmlinux/Downloads/Local-First LLM Orchestration.pdf`
- **Ingested:** 2025-11-05

## Architecture Themes
- Emphasizes local inference servers (vLLM, TGI, SGLang, TensorRT-LLM) plus quantization (GPTQ, AWQ, FP8/INT4) to keep latency/cost low while serving multiple models.
- Recommends hybrid routing cascades with thresholds (`ROUTER_PRE_FLIGHT_LIMIT`, `ROUTER_DEPTH_LIMIT`, fail phrases) to escalate from small local models to larger or remote ones only when confidence drops.
- Advocates semantic cache tiers (L1 answer, L2 compressed span, L3 raw chunk) to short-circuit repeat questions before hitting the retriever.
- Proposes integrating deep-research workflows for high-stakes factual queries, combining local retrieval, structured web search, and verifier chains.

## Key Configuration Knobs
- Environment-driven router knobs: `ROUTER_CONTEXT_LIMIT`, `ROUTER_NODE_LIMIT`, `ROUTER_FAIL_PHRASES`, `ROUTER_MIN_ANSWER_TOKENS`, `MAX_REQUEST_COST`.
- Model tier mapping: `MODEL_SMALL`, `MODEL_BIG`, `MODEL_REMOTE` (local 7B/14B, large local, cloud fallback).
- Optional modules: `CACHE_ENABLED`, `RERANK_ENABLED`, `DEEP_RESEARCH_ENABLED`, `VERIFIER_ENABLED`, `MAX_RETRY_DEPTH`.
- Mode recipes provided for cost-first, balanced, and max-quality; toggle cascades, cache, and verifier according to use case.

## Implementation Highlights
- Step-by-step plan covers router upgrades (multi-armed policies, confidence scoring), retriever tightening (AST-aware chunking, locality-sensitive hashing), semantic cache manager, backend adapters, and telemetry.
- Encourages consistent logging: cost rollups, latency histograms, routing traces, cache hit/miss metrics.
- Security guidance: isolate local inference servers, manage API keys via env vars, log sanitization, and enforce least privilege for automation scripts.
- Rollout strategy: start with cron/tmux automation, add systemd for permanence, then scale to multi-project orchestrators.

## Follow-ups for LLMC
- Audit current router env defaults in `scripts/router.py` against the recommended knob set.
- Evaluate feasibility of adding L1/L2 semantic cache tiers before embedding-heavy refreshes.
- Review failed enrichment payloads to ensure cascaded routing handles malformed JSON gracefully.
- Consider shipping predefined “Cost saver / Balanced / Max quality” `.env` templates so users can switch modes quickly.

