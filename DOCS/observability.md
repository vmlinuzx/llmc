# LLMC MCP Observability Quickstart

## Enabling Observability

Observability is disabled by default. Enable it via `llmc.toml` or environment variables.

### Configuration (`llmc.toml`)

```toml
[mcp.observability]
enabled = true
log_format = "json"  # or "text"
metrics_enabled = true
csv_token_audit_enabled = true
csv_path = "./artifacts/mcp_token_audit.csv"
```

### Environment Variables

Overrides `llmc.toml`:

- `LLMC_MCP_OBS_ENABLED=1`
- `LLMC_MCP_OBS_LOG_FORMAT=json`
- `LLMC_MCP_OBS_CSV_ENABLED=1`

## Logs

When `log_format = "json"`, logs are emitted to stderr in JSON Lines format.

```bash
# Example tailing
tail -f mcp.log | jq .
```

**Key Fields:**
- `ts`: Timestamp (UTC ISO)
- `level`: Log level
- `cid`: Correlation ID (traces a request)
- `tool`: Tool name (if applicable)
- `status`: "ok" or "error"
- `latency_ms`: Execution time
- `session_id`: Session ID from `LLMC_TE_SESSION_ID`

## Metrics

Query metrics using the `get_metrics` tool:

```bash
# Via MCP client
mcp_call get_metrics {}
```

**Response Example:**
```json
{
  "uptime_s": 120.5,
  "total_requests": 42,
  "error_rate": 0.02,
  "tools": {
    "read_file": {
      "calls": 20,
      "avg_ms": 15.4,
      "errors": 0
    }
  }
}
```

## Token Audit

If enabled, a CSV file is written to `csv_path`.

**Columns:**
- `timestamp`
- `correlation_id`
- `tool`
- `tokens_in` (estimated)
- `tokens_out` (estimated)
- `latency_ms`
- `success`
