# Routing Policy Overview

LLMC enrichments now route across three tiers automatically:

1. **Qwen 7B** – default fast path for small spans.
2. **Qwen 14B** – higher-capacity local fallback for medium/complex spans.
3. **GPT-5 nano (Azure/Gemini)** – remote safety net for large / highly nested spans or truncation cases.

## Thresholds

Pre-flight checks (skip local completely and go straight to nano):

- `(tokens_in + tokens_out) > ROUTER_PRE_FLIGHT_LIMIT` (default `28,000`).
- `node_count > ROUTER_NODE_LIMIT` (default `800`).
- `schema_depth > ROUTER_DEPTH_LIMIT` (default `6`).
- `array_elements > 5,000` or `csv_columns > 60`.

Start tier selection (when pre-flight passes):

- `line_count ≤ 60` **and** `nesting_depth ≤ ROUTER_NESTING_LIMIT` (default `3`) → start on **7B**.
- `60 < line_count ≤ 100` **or** `nesting_depth > 3` → start on **14B**.
- `line_count > 100` → start on **14B** unless pre-flight sends straight to nano.
- RAG retrieval with `k == 0` or `avg_score < 0.25` promotes one tier (7B → 14B).

Failure promotion rules (one retry):

- 7B truncation/length → skip 14B → **nano**.
- 7B parse/validation → **14B**, then **nano** if 14B fails.
- 14B truncation or validation → **nano**.
- All tiers clip `usage_snippet` to ≤ 12 lines prior to schema validation.

## CLI & Environment Knobs

| CLI flag | Env var | Description |
| --- | --- | --- |
| `--router=on|off` | `ROUTER_ENABLED` | Disable to force manual tier selection. |
| `--start-tier` | `ROUTER_DEFAULT_TIER` | Override starting tier (`auto` honours policy). |
| `--max-tokens-headroom` | `ROUTER_MAX_TOKENS_HEADROOM` | Reserve context headroom (default 4,000 tokens). |
| – | `ROUTER_PRE_FLIGHT_LIMIT` | Hard cap for `(tokens_in + tokens_out)`; default 28,000. |
| – | `ROUTER_NODE_LIMIT`, `ROUTER_DEPTH_LIMIT`, `ROUTER_LINE_THRESHOLDS` | Tune structural thresholds. |
| – | `ROUTER_PROMOTE_ONCE` | Set to `0` to suppress second promotion (default `1`). |

## Ledger

Each enrichment appends a JSON line to `logs/run_ledger.log`:

```
{"timestamp":"…","task_id":"sha256:…","tier_used":"7b","promo":"none","line_count":42,"nesting_depth":2,"tokens_in":980,"tokens_out":1200,"k":null,"avg_score":null,"result":"pass","reason":"success","wall_ms":18452}
```

See `logs/run_ledger.sample` for a brief before/after example.

