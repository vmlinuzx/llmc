# Roadmap (Template)

## Phases
- P0 – Immediate: critical bugs, auth, deploy blockers
- P1 – Core: main feature set, happy-path flows
- P2 – Quality: performance, DX polish, observability, docs
- P3 – Nice-to-have: experiments, stretch goals

## Current Priorities
- [ ] ~~Ship the template builder MVP~~ (Next.js App Router UI) that builds Codex-ready zips based on orchestration choices. **[IN BETA]**
- [ ] Deliver the first vertical slice end-to-end using the new template + RAG-aware workflow.

## Recently Completed
- [x] Pipe RAG planner output into `codex_wrap.sh` / `llm_gateway.js` so Codex, Claude, and Gemini consume indexed spans automatically before answering.
- [x] Define MVP scope (generic web UI, templated configs, Codex-ready zip).
- [x] Lock technical choices (Next.js App Router, Prisma/Postgres, NextAuth, Docker/Compose, fully OSS stack).
- [x] Automate RAG freshness via cron-friendly wrapper (`scripts/rag_refresh_cron.sh`) + docs/locks/logs.
- [x] Replace MiniLM embeddings with `intfloat/e5-base-v2` across the indexing/query stack (`rag embed`, `rag search`, `rag benchmark`), keeping legacy presets as feature-flag fallbacks.

## Backlog
- [x] **Clean up template repositories** - COMPLETED! 🎉
  - Action: Strip all temp files, cache, binaries, and env files; keep only clean template source
  - Result: 91% context zip reduction (38-46MB → 4.2MB), removed 11,833+ lines of bloat
  - Impact: Clean repo, improved DX, eliminated security risks from leaked API keys
  - See: `.trash/MISSION_ACCOMPLISHED.md` for full details
- [x] **CRITICAL P0: Fix RAG daemon enrichment producing FAKE data** ✅ VERIFIED WORKING!
  - Issue: `llmc-rag-service` daemon calls `rag enrich --execute` which uses `default_enrichment_callable()` that generates FAKE auto-summaries instead of calling real LLMs
  - Root Cause: `tools/rag/service.py:226` uses CLI instead of `scripts/qwen_enrich_batch.py` which has smart routing logic
  - Impact: Daemon produces 100% useless enrichment data, loses all routing (7b→14b→nano), no GPU monitoring, no metrics, no retry logic
  - Fix: Updated daemon to call proper enrichment script with routing logic
  - Status: VERIFIED ✅ - daemon now produces real LLM enrichment with full routing and metrics
  - Test Results (2025-11-12 18:16):
    * 116 detailed enrichments (>50 chars) - REAL data!
    * Real models active: qwen2.5:7b, qwen2.5:14b
    * Smart routing: tier "7b" confirmed
    * Metrics: 1.5MB logs/enrichment_metrics.jsonl, 23.59 tokens/sec
    * Token savings: 368,900 saved (78% reduction)
    * Performance: 1,054/1,349 spans enriched (78% rate)
- [x] **Investigate RAG integration architecture** ✅ COMPLETE
  - Problem: RAG is called at MULTIPLE layers (wrapper scripts, gateway, helper scripts) creating duplication
  - Investigation Result: Keep wrapper-owned architecture (Phase 2 decision was correct)
  - Current State: RAG in wrappers (claude/codex/gemini), gateway is pure routing
  - Issue: 3 different rag_plan_snippet() implementations with code duplication
  - Next: Create scripts/rag_common.sh to standardize implementation
  - See: `rag_architecture_investigation_results.md` for full analysis and recommendations
- [ ] **Implement RAG architecture standardization** - Create shared library to eliminate code duplication
  - Create scripts/rag_common.sh with standardized rag_plan_snippet() function
  - Update claude_wrap.sh, codex_wrap.sh, gemini_wrap.sh to source rag_common.sh
  - Fix silent failures (remove 2>/dev/null, add proper error logging)
  - Fix environment variable inconsistencies (claude_wrap uses CODEX_WRAP_DEBUG incorrectly)
  - Standardize RAG_PLAN_LIMIT, RAG_PLAN_MIN_SCORE, RAG_PLAN_MIN_CONFIDENCE
  - Test all wrappers work correctly
- [ ] **Automate RAG/sidecar asset regeneration** - move `scripts/contracts_build.py` + `scripts/contracts_validate.py` execution from LLM-initiated to background script execution as part of enrichment runs
  - Rationale: reduce LLM involvement in routine asset regeneration; ensure sidecars stay fresh automatically
  - Pipeline: enrichment tick → sync docs → rebuild sidecars → validate → update RAG context
  - Trigger: hook into existing `rag_refresh_cron.sh` or enrichment pipeline
- [ ] Performance profiling baseline
- [ ] Error tracking and alerts
- [ ] Accessibility pass (keyboard, color contrast)
- [ ] Add lightweight spec compressor as post-filter (Option B: architect → compressor → Beatrice)
  - Rationale: preserve user's natural language context for architect; compress verbose output before Beatrice
  - Pipeline: User → Architect (full context) → Compressor (7B bullet-only rewrite) → Beatrice (compressed spec)
  - Bypass flag: SPEC_COMPRESS=off for debugging
  - Target: ≤700 tokens, ≤12 words/bullet, preserve symbols/paths/limits
- [ ] Ship drop-in compressor script (`scripts/spec_compress.sh`) and wire before Beatrice
  - Shell helper calls local Ollama (model env `OLLAMA_COMPRESS_MODEL`, default `qwen2.5:7b-instruct`) with fixed SPEC COMPRESSOR prompt.
  - Pipeline change: run verbose spec through compressor, use fallback when empty, then forward to Beatrice.
- [ ] Add guardrails for spec brevity before dispatching to Beatrice
  - Append `BREVITY_SCORE: <0–10>` on architect output; drop score line if <8.
  - Estimate token budget locally (`len/4`); if >900 tokens, auto-compress before send.
  - Enforce no-prose check: if any line >80 chars, re-run compressor.
- [ ] Nice-to-haves for rewrite efficiency (fast wins)
  - Add `REWRITE_REQUEST=1` branch in `codex_wrap.sh` that runs prompts through a tiny “robot syntax” rewriter (≤30 words). Reuse compressor infra.
  - Log `pre_tokens`, `post_tokens`, `compression_pct` to metrics for savings visibility.
  - Maintain a do/don’t one-pager with 2–3 compressed examples agents can reference.
- [ ] Research how to best leverage available system tools (codex/gemini wrappers, local CLIs)
  - Inventory existing helper scripts (`codex_wrap`, `gemini_wrap`, spec compress) and document when to use each.
  - Identify gaps where desktop commander / tmux / local CLIs can automate more of the pipeline.
- [ ] Swap in concise architect system prompt enforcing the new spec schema
  - System: SYSTEM ARCHITECT (CONCISE MODE) with fixed sections (GOAL, FILES, FUNCS, POLICY, TESTS, RUNBOOK, RULES).
  - Enforce bullet-only output, ≤900 tokens, no prose; prefer symbols/paths/constants; use "TBD" when unsure.
- [ ] Implement AST-driven chunking (Python, TS/JS, Bash, Markdown) using tree-sitter spans, recursive splitting for oversize nodes, and parent/child metadata so retrieval stays semantically aligned.
- [ ] Ship the local model optimization plan: curate Q4_K_M/AWQ builds for Qwen 7B/14B, script GPU offload knobs for WSL2, add routing telemetry for OOMs/latency, and document the three-tier escalation policy.
- [ ] Introduce the semantic cache manager (GPTCache-style) with L3 raw chunk, L2 compressed chunk, and L1 answer tiers; expose hit-rate metrics, eviction hooks, and config toggles before gating production traffic.

## Post-MVP
- [ ] Consolidate enrichment/runtime flags (e.g., `--router off`, `--start-tier 7b`, `--max-spans 0`) into a shared configuration file, document the schema, and add coverage tests that prove the config-driven flow reproduces the scripted defaults.
- [ ] Build GUI configuration tool for compressor settings (Post-MVP)
  - Expose: compressor toggle, token limits, aggressiveness slider
  - Per-repo/per-user profiles: "research-heavy" (50MB docs), "code-only" (minimal compression)
  - Preview mode: show before/after with token savings estimate
  - Preset templates: "aggressive", "balanced", "minimal"

Notes
- Keep items small (1–3 days each)
- Update weekly; archive completed under a “Done” section
