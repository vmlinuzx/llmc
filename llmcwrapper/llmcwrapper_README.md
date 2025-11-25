# llmcwrapper

**A tiny, unix‑style wrapper around LLM providers** with two reliable entrypoints and a shared adapter.  
It replaces brittle shell scripts with a small, testable Python package.

- `llmc-yolo` → fast lane (no RAG, no tools)  
- `llmc-rag`  → retrieval lane (RAG on, tools allowed)  
- `llmc-doctor` → config/health check  
- `llmc-profile` → show/set active profile

## Why?

Shell wrappers rot fast: flags drift, envs collide, and providers change APIs.  
`llmcwrapper` centralizes invariants, provider capabilities, telemetry, and config resolution so your TUIs and scripts call **one** adapter that “just works.”

## What it does

- Resolves config from defaults → user TOML → project TOML → overlays → one‑off `--set/--unset`
- Enforces mode invariants (YOLO = no RAG/tools; RAG = RAG reachable unless `--force`)
- Routes to a provider driver (Anthropic wired; MiniMax scaffold)
- Emits per‑run snapshots and JSONL telemetry under `.llmc/runs/<corr_id>/`
- Optional cost estimation (config‑driven pricing)

## Architecture (at a glance)

```text
             +-------------------+
             |   TUIs / Scripts  |
             +----------+--------+
                        |
                        v
                +-------+--------+
                |   CLI layer    |  llmc-yolo / llmc-rag / llmc-doctor / llmc-profile
                +-------+--------+
                        |
                        v
                +-------+--------+
                |   Adapter      |  invariants, capability checks,
                | (send(...))    |  config merge, telemetry, corr_id
                +---+-------+----+
                    |       |
         +----------+       +------------+
         v                               v
  +------+--------+               +------+--------+
  | Provider:     |               | Provider:     |
  | Anthropic     |               | MiniMax       |
  | (HTTP wired)  |               | (scaffold)    |
  +------+--------+               +------+--------+
         |
         v
  .llmc/runs/<corr_id>/
    ├── resolved-config.json
    └── events.jsonl
```

## Install

```bash
# from the product folder (not your monorepo root)
cd ~/src/llmc/llmcwrapper
python -m pip install -e .
```

## Quick start

```bash
# Health check
llmc-doctor

# YOLO lane (no RAG/tools). Great for smoke tests.
llmc-yolo --profile yolo --dry-run

# RAG lane. If your RAG server isn’t up, force past the check.
llmc-rag --dry-run --force

# Make 'yolo' your shell default
eval "$(llmc-profile set yolo)"

# Show the merged config for a profile
llmc-profile show --profile yolo
```

**Outputs:** each run prints a `corr_id` and writes artifacts:

```
.llmc/runs/<corr_id>/
  ├─ resolved-config.json   # final merged config used for the run
  └─ events.jsonl           # start/provider/cost/dry-run events
```

## Configuration

Config merges in this order:

1. Built‑in defaults  
2. `~/.config/llmc/config.toml` (user)  
3. `./.llmc/config.toml` (project)  
4. `--overlay /path/to/file.toml` (zero or more)  
5. `--set key=value` / `--unset key` and env `LLMC_SET='a.b=1,c.d="x"'`

**Example user config:**

```toml
# ~/.config/llmc/config.toml
[defaults]
profile = "daily"

[profiles.daily]
provider = "minimax"
model = "m2-lite"
[profiles.daily.rag]
enabled = false
[profiles.daily.tools]
enabled = false

[profiles.yolo]
provider = "minimax"
model = "m2-lite"
[profiles.yolo.rag]
enabled = false
[profiles.yolo.tools]
enabled = false
```

**Overlays** are additive TOMLs you can pass per run:

```toml
# ~/overlays/minimax_only.toml
[profiles.daily]
provider = "minimax"
model = "m2-lite"

[profiles.yolo]
provider = "minimax"
model = "m2-lite"
```

Use with:

```bash
llmc-yolo --dry-run --overlay ~/overlays/minimax_only.toml
llmc-doctor --overlay ~/overlays/minimax_only.toml
```

## Modes & invariants

- **YOLO:** `rag.enabled=false` and `tools.enabled=false` (adapter throws unless `--force`)
- **RAG:**  `rag.enabled=true` and RAG server reachable (or `--force` to bypass)

## Provider drivers

- **Anthropic:** Messages API v1 (requires `ANTHROPIC_API_KEY`).  
- **MiniMax:** placeholder; returns a stubbed response (safe for dry‑runs).  
  Add your endpoint/headers in `llmcwrapper/providers/minimax.py` to go live.

## Common commands

```bash
# Run YOLO with one-off changes (degenerate override)
llmc-yolo --dry-run --set profiles.yolo.temperature=0.2

# Shadow compare (logs only, no merge)
llmc-yolo --dry-run --shadow-profile yolo

# Force RAG when server is down
llmc-rag --dry-run --force
```

## Troubleshooting

- **“Multiple top-level packages discovered”** during install: run `pip install -e .` from this **folder**, not your monorepo root, or set explicit packages in `pyproject.toml`.
- **`llmc-yolo` fails:** your active profile has RAG/tools enabled; use `--profile yolo` or
  `--set profiles.<name>.rag.enabled=false --set profiles.<name>.tools.enabled=false`.
- **`llmc-rag` fails:** start your RAG server or add `--force`.
- **No console scripts:** ensure your venv is active (`which llmc-yolo` points inside `.venv/bin`).

## Roadmap

- MiniMax HTTP driver + streaming shim  
- Auto-fallback to YOLO when RAG is unreachable (warn + switch)  
- `--message` and `--stdin` to send arbitrary prompts  
- Record/replay fixtures for CI without live provider calls
