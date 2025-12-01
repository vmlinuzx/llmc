
# MCP MVP — Inputs Locked (Direct Exposure, RAG-First)
*Updated: 2025-12-01T18:05:57*

## Decisions (from you)
1. **Topology:** Direct exposure on your home IP with a local domain name. Reverse proxy optional for MVP. Hairpin relay goes on the roadmap.
2. **Auth:** Keep it simple for MVP — **static bearer token** (`X-LLMC-Token`) loaded from env; no rotation. (mTLS/HMAC added later if needed.)
3. **Tool Surface:** **Full filesystem `/`** and **`run_cmd` allowed** for MVP (you accept the risk). We’ll make these toggles in config, defaulting to **ON** for your env.
4. **RAG Contract:** Treat MCP’s RAG as a **bootloader** that defers to **AGENTS.md**/**CONTRACTS.md** conventions. Provide a thin adapter only.
5. **Envelopes/Handles/Freshness:** **Out of scope for MCP MVP.** LLMC already handles freshness rules in AGENTS.md; MCP will pass raw data through.
6. **Errors/Statuses:** Use standard HTTP error model (401/403/413/422/429, etc.).
7. **Performance Budgets:** You’re fine with sane defaults; we’ll set them.

## Defaults I’ll bake into the HLD (so you don’t have to think about it)
- **Ports/Host:** `:8080` locally; optional reverse proxy at `:443` if certs exist.
- **TLS:** Allowed but **not required** for MVP (you’re on trusted LAN); HSTS/TLS-only moves to roadmap.
- **Auth header:** `X-LLMC-Token: <secret>` (single shared secret, no rotation).
- **Timeouts:** Request read 10s; idle 60s; tool exec 30s (configurable).
- **Perf budgets:** no-op p95 ≤ 15ms; single tool call p95 ≤ 150ms; concurrency cap per client 8; rate 10 r/s (burst 20). Tuned via config.
- **Logging:** JSON, info level; **no redaction** for MVP since it’s your box; retention unbounded (your call). Redaction/retention policies go to roadmap.
- **Data egress:** **Allowed.** No envelope truncation; raw payloads may return.
- **Outbounds:** Allowed by default (since `run_cmd` is on). We’ll add an outbound allowlist later.
- **Config:** `llmc.toml` + env overrides.

## RAG Bootloader (MVP) — Thin Contract
- `rag.search(q, scope: "repo"|"docs"|"both", k=3, budget_tokens=600)` returns `{snippets[], provenance}`
- `rag.bootload(session_id, task_id)` returns minimal plan/scope derived from AGENTS.md/CONTRACTS.md
- No caching; no freshness enforcement here — **LLMC owns it**.

## Non-Goals (explicitly deferred to roadmap)
- Hairpin relay transport
- mTLS/HMAC w/ rotation
- Envelopes/handles & staleness re-validation
- Policy/ACL model (actions/locations/data types/egress)
- TE wrappers (rg/grep/cat)
- Dynamic tool filtering & differential prompts
- Anti-stomp coordination

## Final “Ship/No-Ship” Gates for MVP
- Server runs with static bearer token auth; accepts direct calls from Claude/ChatGPT tools.
- RAG bootloader returns minimal, budgeted context tied to AGENTS.md/CONTRACTS.md.
- Tool calls across `/` and `run_cmd` work on your host.
- Benchmarks show ≥ 40% token reduction vs Desktop Commander baseline (thanks to no pre-prompt bloat and LLMC-side context).

---

If this matches your intent, I’ll draft the HLD against **these exact assumptions** and keep the blast radius small.
