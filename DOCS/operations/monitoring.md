# Monitoring and Observability

Monitoring LLMC ensures your RAG system remains healthy, performant, and cost-effective.

## Service Monitoring

### Status Dashboard

The quickest way to check system health is via the CLI status command:

```bash
llmc-cli service status
```

This displays:
- Service PID and uptime
- Registered repositories
- Indexing status (enriched/embedded counts)
- Last cycle timestamp

### Live Logs

For real-time activity monitoring:

```bash
llmc-cli service logs -f
```

## Metrics

LLMC tracks key performance indicators (KPIs) stored in the internal database.

### Index Stats

View the current state of your index:

```bash
llmc-cli analytics stats
```

Metrics include:
- Total indexed files
- Total spans
- Embedding coverage
- Enrichment coverage

### Enrichment Status

Monitor the background enrichment queue:

```bash
llmc-cli debug enrich-status
```

This shows:
- Queue depth
- Processing rate (tokens/sec)
- Model latency
- Cost accumulation

## Health Checks

Run the "Doctor" tool to diagnose configuration or connectivity issues:

```bash
llmc-cli debug doctor
```

The doctor checks:
- Database integrity
- Embedding model availability
- LLM provider connectivity
- File permission issues

## TUI Dashboard

For a visual overview, use the Terminal User Interface:

```bash
llmc-cli tui
```

The **Monitor** tab provides a live updating view of all the above metrics.

## See Also

- [RAG Daemon](daemon.md)
- [Troubleshooting](troubleshooting.md)
