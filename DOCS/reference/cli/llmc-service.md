# llmc service

The `llmc service` command group manages the RAG background daemon.

## Commands

### `start`

Start the service daemon.

```bash
llmc service start --daemon
```

### `status`

Check the status of the service and registered repositories.

```bash
llmc service status
```

### `stop`

Stop the background service.

```bash
llmc service stop
```

### `logs`

View the service logs.

```bash
llmc service logs -f
```

### `repo`

Manage the list of repositories tracked by the service daemon.

```bash
llmc service repo add /path/to/repo
llmc service repo list
llmc service repo remove /path/to/repo
```
