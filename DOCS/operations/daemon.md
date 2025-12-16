# RAG Daemon Operations

The LLMC RAG Daemon (`llmc-rag-service`) is a background process responsible for keeping your semantic index fresh. It monitors registered repositories for changes, enriches new code with LLM-generated summaries, and updates the vector database.

For most users, the daemon is managed via the unified `llmc-cli`.

---

## Daemon Management

The daemon runs as a user-level background service. It is designed to be lightweight (~0% CPU when idle) and event-driven.

### Starting the Daemon

To start the daemon:

```bash
llmc-cli service start
```

This command will:
1.  Check if any repositories are registered.
2.  Install a systemd user unit (`llmc-rag.service`) if available.
3.  Start the service in the background.

**Note:** If `systemd` is not available (e.g., inside some Docker containers or on macOS without launchd integration), it will fall back to a detached background process.

### Stopping the Daemon

To stop the service:

```bash
llmc-cli service stop
```

### Checking Status

To check if the service is running and view the status of tracked repositories:

```bash
llmc-cli service status
```

Output example:
```text
Status: 🟢 running (PID 12345)
Repos tracked: 2

  📁 llmc
     Path: /home/user/src/llmc
     Spans: 450
     Enriched: 448
     Embedded: 448
```

---

## Configuration

The daemon is configured via the `[daemon]` section of your global `llmc.toml` (usually in the root of your workspace or project).

### Key Settings

```toml
[daemon]
# Service Mode: "event" (inotify) or "poll" (legacy)
mode = "event"

# Event-Driven Settings
debounce_seconds = 2.0             # Wait 2s after last file change before processing
housekeeping_interval = 300        # Run maintenance (vacuum, logs) every 5 minutes

# Idle Enrichment (runs when no file changes are detected)
[daemon.idle_enrichment]
enabled = true
batch_size = 10
interval_seconds = 600             # Minimum 10 minutes between idle runs
max_daily_cost_usd = 1.00          # Budget cap for cloud models
```

### Modes

-   **Event Mode (`mode = "event"`):** Uses `inotify` to watch for file system events. This is the recommended mode as it uses negligible CPU when idle.
-   **Poll Mode (`mode = "poll"`):** Periodically scans the file system. Use this only if `inotify` is unavailable or if you are on a file system that doesn't support events (e.g., some network mounts).

---

## Logging & Monitoring

### Viewing Logs

To view the service logs in real-time:

```bash
llmc-cli service logs -f
```

This wraps `journalctl` (on systemd systems) or `tail -f` (on others).

### Log Locations

If you need to access the raw log files:

-   **Systemd (Linux):** Managed by journald.
    ```bash
    journalctl --user -u llmc-rag.service
    ```
-   **File Fallback:** `~/.llmc/logs/rag-daemon/rag-service.log`
-   **Structured Logs:** `logs/` directory in your project root (if configured in `[logging]`).

### Health Checks

To verify that the daemon can connect to your LLM provider (e.g., Ollama):

```bash
llmc-cli service health
```

This checks connectivity to the endpoints defined in your configuration.

---

## Service Integration

### Linux (Systemd)

On Linux systems with `systemd`, the daemon automatically installs a user service unit at:
`~/.config/systemd/user/llmc-rag.service`

**Auto-start on Login:**

To ensure the daemon starts automatically when you log in:

```bash
llmc-cli service enable
```

To disable auto-start:

```bash
llmc-cli service disable
```

### macOS / Other

On macOS or systems without `systemd`, the `llmc-cli service start` command uses a fallback mechanism (process forking). Currently, native `launchd` integration is not automatically installed by the CLI, but the fallback mode is sufficient for most session-based usage.