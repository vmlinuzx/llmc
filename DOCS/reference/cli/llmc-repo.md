# llmc repo

The `llmc repo` command group manages the repository registry and workspaces.

## Commands

### `register`

Register a repository with LLMC and create its workspace.

```bash
llmc repo register /path/to/repo
```

### `list`

List all registered repositories.

```bash
llmc repo list --json
```

### `rm`

Unregister a repository.

```bash
llmc repo rm /path/to/repo
```

### `validate`

Validate a repository's configuration.

```bash
llmc repo validate /path/to/repo
```
