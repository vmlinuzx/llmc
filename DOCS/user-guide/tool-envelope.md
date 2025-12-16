# TE Analytics

Separate analytics tool for Tool Envelope telemetry data.

## Why Separate?

`te` itself needs to be lightweight - minimal overhead for every command execution.  
`te-analyze` is for deep-dive analysis and can take its time.

## Commands

### Summary
```bash
./scripts/te-analyze summary [--days N]
```
Shows overall stats: total calls, unique commands/agents, mode breakdown, latency, output size.

### By Command
```bash
./scripts/te-analyze by-command [--days N] [--limit N]
```
Breakdown by command and mode: count, avg latency, total output.

### By Agent
```bash
./scripts/te-analyze by-agent [--days N]
```
Breakdown by agent_id (set via `TE_AGENT_ID` env var).

### Enrichment Candidates
```bash
./scripts/te-analyze candidates [--days N] [--limit N]
```
Shows pass-through commands that might benefit from enrichment, ordered by total output size.  
**This is your priority list for what to build next.**

### Slow Commands
```bash
./scripts/te-analyze slow [--days N] [--limit N]
```
Shows slowest commands by avg latency.  
**This is your optimization priority list.**

### Raw Query
```bash
./scripts/te-analyze query "SELECT ..."
```
Execute any SQL query against the telemetry database.

## Database Schema

Location: `.llmc/te_telemetry.db`

```sql
CREATE TABLE telemetry_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    cmd TEXT NOT NULL,
    mode TEXT NOT NULL,           -- enriched | passthrough | raw | error
    input_size INTEGER NOT NULL,
    output_size INTEGER NOT NULL,
    truncated INTEGER NOT NULL,
    handle_created INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    error TEXT
);
```

## Example Workflow

1. **Generate some telemetry:**
   ```bash
   export TE_AGENT_ID="claude-dc"
   te ls -la
   te grep "pattern" .
   te pwd
   ```

2. **Check summary:**
   ```bash
   te-analyze summary
   ```

3. **Find enrichment priorities:**
   ```bash
   te-analyze candidates --limit 5
   ```
   → This tells you which commands LLMs use most that would benefit from enrichment

4. **Check performance:**
   ```bash
   te-analyze slow --limit 5
   ```
   → This tells you what's slow and needs optimization

5. **Custom analysis:**
   ```bash
   te-analyze query "SELECT agent_id, cmd, COUNT(*) FROM telemetry_events GROUP BY agent_id, cmd"
   ```

## Integration with TUI

The TUI can read from the same SQLite database to show real-time analytics dashboards.

## Future Ideas

- Token cost estimation (output_size / 4 * price_per_token)
- Savings calculation (compare enriched vs passthrough for same command)
- Time-series graphs (calls over time, latency trends)
- Export to JSON/CSV for external tools
- Alerting on anomalies (sudden latency spikes, error rates)
