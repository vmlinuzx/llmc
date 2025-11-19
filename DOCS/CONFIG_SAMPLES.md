# Config Samples

## Daemon config (`examples/config/daemon.sample.yaml`)

```yaml
repos_root: /data/repos
workspaces_root: /data/workspaces

policy:
  readonly: false
  dry_run: false
  denylist_prefixes:
    - /etc
    - /proc
    - /sys
    - /dev
```

## Registry (`examples/config/registry.sample.yaml`)

```yaml
repos:
  - name: llmc
    repo_path: ./llmc
    rag_workspace_path: .llmc/workspace
```

## Environment (`examples/.env.sample`)

```dotenv
LLMC_DEFAULT_WORKSPACE=.llmc/workspace
LLMC_DEFAULT_EXPORTS=exports
```

