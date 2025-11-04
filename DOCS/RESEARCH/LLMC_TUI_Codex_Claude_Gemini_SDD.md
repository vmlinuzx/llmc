# LLMC TUI — Codex/Claude/Gemini

**Software Design Document (SDD)**  
Status: Draft v1  
Date: Nov 4, 2025  
Owner: DC (WPSG)  
Editors: LLMC core

## 1. Purpose & Goals

Build a fast, minimal terminal UI (TUI) that lets DC work with three model families (Codex/OpenAI, Claude/Anthropic, Gemini/Google) via the existing LLM Commander stack (router, RAG, MCP tools, semantic cache). The TUI prioritizes:

- Speed & control in a terminal (SSH/mosh friendly, low overhead).
- Deterministic workflows (prompt templates, context slices, agent routes).
- Cost safety (local-first; fall back to APIs with visibility and caps).
- Observability (token/time/cost metrics; reproducible transcripts/artifacts).

Non-goals (v1): rich GUI, image editing, fine-tuning UIs, multi-tenant auth portal.

## 2. User Stories (condensed)

- **U1 — Quick chat:** As DC, I hit `/` to open a composer, select a provider (Codex/Claude/Gemini or Auto), paste a prompt, and see tokens, latency, and cost live.
- **U2 — RAG assist:** I toggle `R` to attach repo/workspace context; I can preview retrieved spans (AST-aligned), exclude any, then send.
- **U3 — Multi-agent run:** I route a task to Beatrice (Codex), Otto (Claude), or Rem (Gemini) with anti-stomp tickets and see tool calls stream in a side pane.
- **U4 — Cost guardrails:** I set a session cap ($/tokens). When exceeded or p95 latency spikes, the router auto-downgrades to local Qwen or asks before continuing.
- **U5 — Repro:** I export an Instruction Pack (prompt + router params + context hashes) and the Run Record (messages, tool calls, metrics) for later replay.
- **U6 — Eval/A-B:** I run the same prompt with two routes (e.g., Claude 3.7 vs Gemini 2.5) and compare answers, scores, and costs side-by-side.

## 3. Design Principles

- Local-first (quantized Qwen 7B/14B) with clear fallbacks to Codex/Claude/Gemini.
- Explain every hop: show router decision, cache hits, RAG sources, tool calls.
- Minimal keystrokes: modal keybindings, mouse optional.
- Paper trail: every run can be exported and replayed deterministically.

## 4. Functional Requirements

### Core

- Multi-provider chat with streaming tokens, stop/abort, regenerate, and seed replay.
- Provider adapters: OpenAI/Codex, Anthropic/Claude, Google/Gemini, Local (Ollama/Qwen).
- Router modes: Auto (policy-based), Pinned (force a provider), Simul (A/B).
- RAG panel: show top-K spans (title/path/symbol/score), inline expand to preview AST slice.
- Tool/MCP panel: list available tools; show call/args/return; allow retry with edits.
- Semantic cache: display L1/L2/L3 hit/miss and reuse decision.
- Cost & token HUD: running totals per session and per run; caps and warnings.
- Transcript & artifact export (JSONL + markdown recap; diffs/artifacts as files).

### Advanced

- Prompt templates library with variables; “recent prompts” palette.
- Session profiles (e.g., Refactor, Write PRD, Data QA) preconfiguring router, RAG, tools.
- Eval harness: run a prompt across N routes; compute latency/cost and optional score rubric.
- Offline mode: local models only; queue remote runs for later (optional).

## 5. Non-Functional Requirements

- **Performance:** p95 time-to-first-token ≤ 1.5s (local), ≤ 3.0s (remote); UI input latency < 50ms.
- **Reliability:** graceful degradation if a provider/tool is down; queued retries.
- **Security:** secrets isolated; redacted logs; no tool call prints secrets by default.
- **Portability:** Linux-first; works over SSH/mosh in 80×24; no GPU hard requirement.
- **Observability:** metrics (Prometheus/OpenTelemetry hooks), structured logs.

## 6. High-Level Architecture

```
TUI (Textual/BubbleTea) 
 ├─ ViewModel (state machine; panes, modals, keymaps)
 ├─ Command Bus (async; debounced actions; cancellation)
 ├─ Client SDK (ProviderAdapter, RouterClient, RAGClient, MCPClient, CacheClient)
 └─ Persistence (sessions, transcripts, artifacts, configs)

External:
LLMC Router ⇄ Provider Adapters (OpenAI/Anthropic/Google/Ollama)
RAG Service (e5-base-v2 embeddings; tree-sitter spans; reranker)
MCP Tool Hub (FS, Git, HTTP, Graph, BigCommerce, NetSuite, …)
Semantic Cache (L3 raw, L2 compressed, L1 answer)
```

## 7. Key Components & Responsibilities

- **TUI Shell:** panes (Chat, RAG, Tools, Metrics, Logs), modals (Settings, Templates).
- **ProviderAdapter:** normalize send/stream/stop; map tokens/cost across vendors.
- **RouterClient:** implements policies (local-first, cost caps, latency SLOs, redlines).
- **RAGClient:** query index; preview spans; user can include/exclude before send.
- **MCPClient:** list/invoke tools; show args/results; allow retry/edit; track cost/time.
- **CacheClient:** probe cache; record hits/misses; expose reuse reason.
- **Exporter:** serialize runs; pack artifacts; write Session Bundle.
- **Config Manager:** layered config (global → workspace → session overrides).

## 8. Provider & Routing Strategy

- **Local tier:** Qwen 7B/14B Q4_K_M (or AWQ); stop-gap answers with low cost.
- **API tiers:** Codex (OpenAI), Claude (Anthropic), Gemini (Google).
- **Routing inputs:** prompt length, task type (code vs prose), required tools, privacy level, cost/latency budget, user pin.

**Example policies:**

- Speed-cheap: local → Claude → Gemini → Codex
- Code-heavy: Claude → Codex → Gemini → local
- Analyze-long doc: Gemini → Claude → Codex → local
- A/B mode: run two routes; merge UI results; capture diffs and rubric scoring.

## 9. RAG & Context

- **Index:** e5-base-v2 (768-dim) with query:/passage: prefixes; cosine; L2-norm.
- **Chunking:** tree-sitter spans (function/class/module), minimal overlap; recurse only if node exceeds token budget; store file, symbol, kind, start, end, summary, docstring, body_hash.
- **Rerank (optional):** small cross-encoder pass on top-K when confidence < τ.
- **TUI UX:** `R` opens RAG pane → shows spans with scores → user toggles inclusion → inline preview (read-only) → back to composer.

## 10. Semantic Cache

- **L3:** raw chunk cache (retrieval results keyed by query hash + index epoch).
- **L2:** compressed chunk cache (summarized spans by purpose).
- **L1:** answer cache (prompt + context + route → final answer).
- TUI shows per-run: cache layer, decision (reuse vs bypass), and savings (tokens/$).

## 11. Tooling (MCP) Integration

- List tools with short descriptions and trust levels.
- Invoke tools inline; show args/return; allow “edit & retry”.
- Safety rails: confirm on dangerous ops; dry-run when available; redact secrets in logs.

## 12. UX & Keybindings (proposal)

- **Global:** `?` help, `Ctrl+P` Command Palette, `:` command line, `Esc` cancel.
- **Chat:** `/` compose, `Enter` send, `Ctrl+R` regenerate, `Ctrl+.` stop.
- **RAG:** `R` open/close, `Space` include/exclude span, `Tab` preview.
- **Providers/Router:** `Alt+1/2/3/4` Local/Claude/Gemini/Codex, `Alt+A` Auto, `Alt+B` A/B.
- **Tools:** `T` list, `Enter` invoke, `E` edit last args, `L` view logs.
- **Metrics:** `M` toggle HUD, `S` settings, `X` export Session Bundle.

## 13. Configuration (schema outlines, no code)

- **Providers:** API base, model IDs, timeouts, max_output_tokens, safety setting.
- **Router:** tiers order, budget caps ($, tokens), p95 latency targets, redline actions.
- **RAG:** index path, K, rerank on/off, confidence threshold, repo/workspace roots.
- **Cache:** L1–L3 on/off, TTLs, max size, eviction policy, bypass list.
- **Telemetry:** enabled, endpoint, sampling, redaction rules.
- **Security:** secret sources (env, keyring), allowed outbound hosts, offline mode.

## 14. Observability & Telemetry

- Per-run metrics: time-to-first-token, total latency, tokens in/out, $ spent, cache hits.
- Per-provider health: success rate, p95 latency, throttles/errors.
- Router decisions: reason codes (cost cap, latency SLO, model pin, failure).
- Export logs: structured JSONL + compact human summary.

## 15. Security & Privacy

- Secrets never printed; masked in UI/logs.
- “Private mode”: disable remote providers, disable tool network calls; local-only RAG.
- Domain allowlist for network tools; warn on exfiltration risk (large paste + external POST).
- Session purge command to wipe logs/artifacts/embeddings for sensitive workspaces.

## 16. Performance Targets & Sizing

- **UI:** draw/refresh ≤ 16ms/frame; streaming updates incrementally.
- **Local:** Qwen 7B target ≥ 15 tok/s; first-token ≤ 1.5s (warm); batch where safe.
- **Remote:** keep concurrent streams ≤ 3 unless pinned; backoff on 429/5xx.

## 17. Failure Handling

- **Provider errors:** show code + retry advice; one-click switch route.
- **Tool errors:** show stderr snippet; offer dry-run or safe defaults.
- **Cache/index mismatch:** detect index epoch; force requery or reindex guidance.

## 18. Data & Artifacts

- **Session:** id, started/ended, config snapshot, cost/metrics, transcript (messages & tool calls).
- **Run:** route, provider, prompt hash, context refs (file/symbol/range), outputs, metrics.
- **Bundle:** `SESSION_YYYYMMDD_HHMM/` with `transcript.jsonl`, `recap.md`, `artifacts/`, `metrics.json`.

## 19. Test Plan (essentials)

- **Unit:** adapters normalize token/cost; router selects expected tier given fixtures.
- **Integration:** stream lifecycle (start/delta/stop); RAG preview & include/exclude.
- **Perf:** TTFT p95 under targets; UI input latency under 50ms at 120 Hz stream.
- **Reliability:** provider outage → fallback; cache correctness; export/import replay.
- **UX:** keymap conflicts in common terminals; 80×24 layout sanity.

## 20. Rollout Plan

- **P0 (2–3 days):** Single-pane chat; Local + one API provider; basic metrics; export bundle.
- **P1:** Router Auto/Pinned/A-B; RAG pane with preview; cache HUD.
- **P2:** Tool/MCP pane; cost caps; profiles/templates; eval harness.
- **P3:** Offline mode; replay runner; team share of Session Bundles.

## 21. Risks & Mitigations

- **Vendor drift / API changes:** version-pin adapters; canary tests nightly.
- **Cost blowouts:** default to local-first; hard session caps; visible cost HUD.
- **Latency regression:** router p95 SLOs; quick provider flip; cache warmers.
- **Context errors:** show exact included spans; easy deselect; keep provenance.
- **Terminal variance:** stick to widely supported keycodes; configurable keymap.

## 22. Open Questions

1. Do we want queued remote runs in offline mode (write now, send later)?
2. Should eval scoring include LLM-as-judge or only heuristic metrics initially?
3. Ship with Python/Textual (fast to iterate) or Go/Bubble Tea (single static binary)?
4. Where to persist Session Bundles by default (repo `.llmc/` vs `~/.llmc/`)?

## 23. Acceptance Criteria (v1)

- Start a session, select route, stream an answer with visible tokens/cost/latency.
- Toggle RAG; preview and include specific spans; answer cites selected spans.
- Switch providers mid-session; router explains decisions with reason codes.
- Export Session Bundle; replay produces identical output (given same providers).
- Hit a session budget cap → TUI blocks further remote calls unless explicitly overridden.

## 24. Implementation Notes (mapping to your stack)

- **Agents:** Beatrice (Codex), Otto (Claude), Rem (Gemini) exposed via Router; anti-stomp tickets shown in Logs pane.
- **Embeddings & Chunking:** e5-base-v2 index; tree-sitter spans with symbol metadata; confidence heuristic drives rerank/use-as-is.
- **Cache:** GPTCache-style tiers; surface hit/miss and savings in HUD; toggle per session.
- **Quant local:** Qwen 7B/14B Q4_K_M presets; num_gpu/num_batch profiles; graceful OOM handling → auto-pin to API if needed.
