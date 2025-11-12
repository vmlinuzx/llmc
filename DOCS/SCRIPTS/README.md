# Scripts Reference Index

Last updated: 2025-11-07

This index catalogs every item under `scripts/` at the top level and links to a dedicated page per script or subfolder. Use this as the single entry point to find usage, flags, environment variables, side effects, and related docs for each tool.

Core orchestration
- `scripts/codex_wrap.sh` — smart router and prompt builder. See: DOCS/SCRIPTS/codex_wrap.sh.md
- `scripts/llm_gateway.js` — local-first LLM gateway with API fallbacks. See: DOCS/SCRIPTS/llm_gateway.js.md
- `scripts/llm_gateway.sh` — thin wrapper around the gateway. See: DOCS/SCRIPTS/llm_gateway.sh.md
- `scripts/claude_wrap.sh` — Claude wrapper with cached context slices. See: DOCS/SCRIPTS/claude_wrap.sh.md
- `scripts/gemini_wrap.sh` — Gemini wrapper (when present). See: DOCS/SCRIPTS/gemini_wrap.sh.md
- `scripts/router.py` — routing heuristics for enrichment tiers. See: DOCS/SCRIPTS/router.py.md

RAG pipeline
- `scripts/indexenrich.sh` — local Ollama indexing + enrichment. See: DOCS/SCRIPTS/indexenrich.sh.md
- `scripts/indexenrichazure.sh` — Azure-backed enrichment. See: DOCS/SCRIPTS/indexenrichazure.sh.md
- `scripts/rag_sync.sh` — sync specific paths into the index. See: DOCS/SCRIPTS/rag_sync.sh.md
- `scripts/qwen_enrich_batch.py` — batch enricher (7B/14B/gateway tiers). See: DOCS/SCRIPTS/qwen_enrich_batch.py.md
- `scripts/rag_plan_helper.sh` — emit planner snippet from stdin. See: DOCS/SCRIPTS/rag_plan_helper.sh.md
- `scripts/rag_plan_snippet.py` — planner + indexed span context. See: DOCS/SCRIPTS/rag_plan_snippet.py.md
- `scripts/rag_refresh.sh` — one-shot refresh (sync → enrich → embed → stats). See: DOCS/SCRIPTS/rag_refresh.sh.md
- `scripts/rag_refresh_watch.sh` — tmux controller for recurring refresh. See: DOCS/SCRIPTS/rag_refresh_watch.md
- `scripts/rag_refresh_cron.sh` — cron-safe wrapper with file locking. See: DOCS/SCRIPTS/rag_refresh_cron.sh.md
- `scripts/start_rag_refresh_loop.sh` — simple while-loop refresher. See: DOCS/SCRIPTS/start_rag_refresh_loop.sh.md

Metrics, logs, and summaries
- `scripts/enrichmentmetricslog.sh` — summarize enrichment metrics. See: DOCS/SCRIPTS/enrichmentmetricslog.sh.md
- `scripts/enrichmenttail.sh` — tail raw enrichment JSONL. See: DOCS/SCRIPTS/enrichmenttail.sh.md
- `scripts/plannermetricslog.sh` — follow planner metrics. See: DOCS/SCRIPTS/plannermetricslog.sh.md
- `scripts/record_enrichment_metrics.py` — structured logging helper. See: DOCS/SCRIPTS/record_enrichment_metrics.py.md
- `scripts/summarize_enrichment_metrics.py` — rollup script. See: DOCS/SCRIPTS/summarize_enrichment_metrics.py.md
- `scripts/summarize_planner_metrics.py` — planner summary. See: DOCS/SCRIPTS/summarize_planner_metrics.py.md
- `scripts/codexlogtail.sh` — tail codex gateway log. See: DOCS/SCRIPTS/codexlogtail.sh.md
- `scripts/gateway_cost_rollup.js` — cost aggregation. See: DOCS/SCRIPTS/gateway_cost_rollup.js.md

Contracts sidecar
- `scripts/contracts_build.py` — build `contracts.min.json`. See: DOCS/SCRIPTS/contracts_build.py.md
- `scripts/contracts_validate.py` — validate checksum/drift. See: DOCS/SCRIPTS/contracts_validate.py.md
- `scripts/contracts_precommit.sh` — convenience wrapper. See: DOCS/SCRIPTS/contracts_precommit.sh.md
- `scripts/contracts_render.py` — slice/adapter renderer. See: DOCS/SCRIPTS/contracts_render.py.md

Utilities
- `scripts/run_in_tmux.sh` — run a command in a named tmux session. See: DOCS/SCRIPTS/run_in_tmux.sh.md
- `scripts/deep_research_ingest.sh` — ingest notes to archive and RAG. See: DOCS/SCRIPTS/deep_research_ingest.sh.md
- `scripts/quick_test.sh` — API smoke checks. See: DOCS/SCRIPTS/quick_test.sh.md
- `scripts/pdf_to_md.sh` — PDF → Markdown helper. See: DOCS/SCRIPTS/pdf_to_md.sh.md
- `scripts/install_ripgrep.sh` — local install helper. See: DOCS/SCRIPTS/install_ripgrep.sh.md
- `scripts/sync_to_drive.sh` — rclone one-way mirror with guards. See: DOCS/SCRIPTS/sync_to_drive.sh.md
- `scripts/integration_gate.sh` — integration gate harness. See: DOCS/SCRIPTS/integration_gate.sh.md
- `scripts/run_mcpo_bridge.sh` — MCP bridge launcher. See: DOCS/SCRIPTS/run_mcpo_bridge.sh.md
- `scripts/tool_health.sh` — detect local CLI/MCP capabilities. See: DOCS/SCRIPTS/tool_health.sh.md
- `scripts/llmc_edit.sh` — apply changeset editing wrapper. See: DOCS/SCRIPTS/llmc_edit.sh.md
 - `scripts/tool_dispatch.sh` — post-process model output and execute on-demand tool calls. See: DOCS/SCRIPTS/tool_dispatch.sh.md
 - `scripts/tool_query.py` — search/describe tools from `.codex/tools.json`. See: DOCS/SCRIPTS/tool_query.py.md
- `scripts/llmc_lock.py` — simple file lock helper. See: DOCS/SCRIPTS/llmc_lock.py.md

Subfolders with their own READMEs
- `scripts/rag/` — RAG development helpers (server, watchers, AST chunker). See: DOCS/SCRIPTS/rag/_index.md
- `scripts/metrics_sinks/` — sink-specific notes. See: DOCS/SCRIPTS/metrics_sinks/_index.md
- `scripts/tests/` — test shims. See: DOCS/SCRIPTS/tests/_index.md
- Existing deep-dives: `scripts/LLM_GATEWAY_README.md`, `scripts/SMART_ROUTING.md` (kept as authoritative).
