# router.py — Enrichment Routing Heuristics

Path
- scripts/router.py

Purpose
- Provide deterministic, configurable heuristics for choosing the starting tier (7B/14B/nano) and escalation on failure during enrichment.

Key functions
- `estimate_tokens_from_text(text)` — rough token estimate (~4 chars/token)
- `estimate_json_nodes_and_depth(text)` — count/approximate JSON complexity
- `estimate_nesting_depth(snippet)` — generic nesting from braces/brackets/parentheses
- `expected_output_tokens(span)` — estimate required output tokens for an enrichment
- `RouterSettings` — tunable thresholds via env (`ROUTER_*`)
- `choose_start_tier(metrics, settings, override)` — decide 7B/14B/nano
- `choose_next_tier_on_failure(failure_type, current_tier, ...)` — promotion policy

Important env
- `ROUTER_CONTEXT_LIMIT`, `ROUTER_MAX_TOKENS_HEADROOM`, `ROUTER_PRE_FLIGHT_LIMIT`
- `ROUTER_NODE_LIMIT`, `ROUTER_DEPTH_LIMIT`, `ROUTER_ARRAY_LIMIT`, `ROUTER_CSV_LIMIT`
- `ROUTER_NESTING_LIMIT`, `ROUTER_LINE_THRESHOLDS` (e.g., `60,100`)
- `ROUTER_DEFAULT_TIER` (optional override: `auto|7b|14b|nano`)

Used by
- `scripts/qwen_enrich_batch.py` (metrics computation + tier selection)

