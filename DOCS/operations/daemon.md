# RAG Daemon Operations

The **RAG Daemon** (`llmc-rag-daemon`) is the heartbeat of LLMC. It runs in the background to ensure your repository indexes stay fresh and synchronized with your code.

## 1. Architecture

The daemon operates as a **Scheduler + Worker** model:
- **Scheduler**: Wakes up every few seconds (the "tick") to check if any registered repositories need work.
- **Workers**: Executes tasks like `index`, `embed`, or `enrich` in a thread pool.

It is typically managed by the **Service Wrapper** (`llmc-rag-service`), which handles PID files, logging, and backgrounding.

## 2. Managing the Service

We recommend using the `llmc-rag-service` CLI for day-to-day operations.

### Start
```bash
# Start in the background (daemon mode)
llmc-rag-service start --interval 300 --daemon

# Start in the foreground (for debugging)
llmc-rag-service start
```

### Stop
```bash
llmc-rag-service stop
```

### Status
```bash
llmc-rag-service status
```
Output:
```text
Service is running (PID 12345)
Managed repos:
  - /home/user/src/llmc
  - /home/user/src/webapp
```

## 3. Configuration

The daemon is configured via `~/.llmc/rag-daemon.yml`. If this file doesn't exist, it uses safe defaults.

**Key Settings:**

```yaml
# How often (seconds) to check for file changes
tick_interval: 300

# Max concurrent jobs (indexing/embedding)
concurrency: 2

# Where to store logs and state
log_dir: "~/.llmc/logs"
state_db: "~/.llmc/rag-service.json"
```

To see the *effective* configuration (defaults + file overrides):
```bash
llmc-rag-daemon config --json
```

## 4. Troubleshooting

### Daemon Doctor
Run the doctor command to check for permissions, path issues, or configuration errors.
```bash
llmc-rag-daemon doctor
```

### Logs
Logs are written to `~/.llmc/logs/rag-daemon.log`.
- **INFO**: Normal cycle updates ("Synced 5 files").
- **ERROR**: Job failures or crashes.

### Clearing Failures
If a repo gets stuck in a failure loop (e.g., due to a syntax error crashing the indexer), you can clear its failure state:

```bash
llmc-rag-service clear-failures --repo /path/to/repo
```
