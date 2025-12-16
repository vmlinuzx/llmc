# llmc-rag-daemon Reference

Generated from `tools.rag_daemon.main --help`

```text
LLMC RAG Daemon

Run the scheduler + workers that keep RAG workspaces fresh.

Usage:
  llmc-rag-daemon [command] [options]

Commands:
  run         Run the daemon until interrupted (default)
  tick        Run a single scheduler tick and exit
  config      Show the effective configuration
  doctor      Run basic health checks (paths, registry, state store)

Global options:
  --config PATH      Path to rag-daemon.yml (default: $LLMC_RAG_DAEMON_CONFIG or ~/.llmc/rag-daemon.yml)
  --log-level LEVEL  DEBUG, INFO, WARNING, ERROR (default from config)

Examples:
  llmc-rag-daemon
  llmc-rag-daemon run --config ~/.llmc/rag-daemon.yml
  llmc-rag-daemon tick
  llmc-rag-daemon config --json

```
