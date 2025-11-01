#!/usr/bin/env node
// gateway_cost_rollup.js - Summarize daily costs from logs/gateway.csv
//
// Produces logs/daily_costs.csv with columns:
//   date,total_cost_usd,calls,avg_latency_ms
//
// Usage: node scripts/gateway_cost_rollup.js [logs_dir]
// Example: node scripts/gateway_cost_rollup.js

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const LOG_DIR = process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, 'logs');
const SRC = path.join(LOG_DIR, 'gateway.csv');
const OUT = path.join(LOG_DIR, 'daily_costs.csv');

if (!fs.existsSync(SRC)) {
  console.error(`[rollup] No input file: ${SRC}`);
  process.exit(0);
}

const lines = fs.readFileSync(SRC, 'utf8').trim().split(/\r?\n/);
if (lines.length <= 1) {
  console.error('[rollup] No data rows found');
  process.exit(0);
}

// ts,provider,model,task_type,latency_ms,in,out,cost_usd,route,ok
const header = lines[0].split(',');
const idx = Object.fromEntries(header.map((h, i) => [h, i]));

const stats = new Map(); // date -> { cost, calls, latency }

for (let i = 1; i < lines.length; i++) {
  const row = lines[i].split(',');
  if (row.length < 10) continue;
  const ts = row[idx['ts']];
  const date = (ts || '').slice(0, 10);
  const cost = parseFloat(row[idx['cost_usd']] || '0') || 0;
  const latency = parseFloat(row[idx['latency_ms']] || '0') || 0;
  if (!date) continue;
  const s = stats.get(date) || { cost: 0, calls: 0, latency: 0 };
  s.cost += cost;
  s.calls += 1;
  s.latency += latency;
  stats.set(date, s);
}

const outLines = ['date,total_cost_usd,calls,avg_latency_ms'];
for (const [date, s] of Array.from(stats.entries()).sort(([a], [b]) => a.localeCompare(b))) {
  const avgLatency = s.calls ? (s.latency / s.calls) : 0;
  outLines.push([date, s.cost.toFixed(6), s.calls, Math.round(avgLatency)].join(','));
}

fs.writeFileSync(OUT, outLines.join('\n') + '\n', 'utf8');
console.log(`[rollup] Wrote ${OUT} (${outLines.length - 1} rows)`);

