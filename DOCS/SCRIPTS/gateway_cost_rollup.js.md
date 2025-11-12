# gateway_cost_rollup.js — Daily Cost Rollup

Path
- scripts/gateway_cost_rollup.js

Purpose
- Summarize `logs/gateway.csv` into `logs/daily_costs.csv` with date, total cost, call count, and average latency.

Usage
- `node scripts/gateway_cost_rollup.js [logs_dir]`

Input schema
- CSV header: `ts,provider,model,task_type,latency_ms,in,out,cost_usd,route,ok`

