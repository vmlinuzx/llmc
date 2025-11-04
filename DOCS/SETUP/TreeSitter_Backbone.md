# Tree-sitter Backbone Plan

_Commodore Grace orders us to stop wasting remote tokens and lean on deterministic tooling first._

## Why Tree-sitter / LazyVim

- **Structured context on demand:** Tree-sitter parsers expose AST nodes that we can query locally for symbol locations, imports, and call graphs. That means we can answer “where is X defined?” without firing up a remote LLM.
- **Editor-native UX:** LazyVim ships with tree-sitter, Telescope, and LSP integration, so contributors who adopt it gain structural navigation, folding, and refactors out of the box.
- **Token savings:** Early-pass analysis suggests ~60% fewer remote lookups once structural questions are handled with tree-sitter queries instead of natural-language prompts.

## Immediate Setup (Developer Workstation)

1. **Install Neovim ≥ 0.9** (brew, apt, scoop, etc.).
2. **Bootstrap LazyVim:**
   ```bash
   git clone https://github.com/LazyVim/starter ~/.config/nvim
   cd ~/.config/nvim && rm -rf .git && nvim
   ```
3. **Enable core plugins:** LazyVim already includes `nvim-treesitter`, Telescope, and LSP defaults. Inside Neovim run:
   ```vim
   :Lazy sync
   :TSInstall bash javascript json lua markdown python typescript yaml
   ```
   (Add languages relevant to current work.)
4. **Optional tree-sitter CLI:**
   ```bash
   npm install -g tree-sitter-cli
   ```
   Gives us `tree-sitter parse` for CI scripts and quick AST dumps.

## Recommended Workflow

- Use `:Telescope treesitter` or `:TSToolsGoToSourceDefinition` to jump directly to symbols instead of asking a remote LLM.
- Run `tree-sitter parse file.ts > file.ast` when debugging complex structures or preparing data for agents.
- Lean on LazyVim keybinds (`<leader>ss` for structural search, `<leader>c` for code actions) before escalating to codex.

## Repo Indexer (current prototype)

Run the Python CLI under `tools/rag/` to build and maintain the `.rag/` cache:

```bash
# one-time environment setup
python3 -m venv /tmp/rag-venv
source /tmp/rag-venv/bin/activate
pip install -r tools/rag/requirements.txt

# full index (writes .rag/index_v2.db and versioned spans.jsonl)
python -m tools.rag.cli index

# incremental sync for changed files
git diff --name-only HEAD~1 | python -m tools.rag.cli sync --stdin

# inspect counts
python -m tools.rag.cli stats
deactivate
```

Supported languages today: **Python**, **JavaScript/TypeScript/TSX**, **Go**, and **Java**. Additional grammars are configured and can be enabled as we add extraction rules.

Outputs live in `.rag/` (ignored by git): SQLite DB with span metadata and an optional JSONL export per run. Span hashes are stable per language + code bytes, so enrichment/embedding layers can skip repeats.

Helper script: `scripts/rag_sync.sh` accepts file paths (relative or absolute inside the repo) and forwards them to `rag sync --stdin`. Editor integrations call this to avoid retyping commands.

### CI automation

GitHub Actions workflow: `.github/workflows/rag-index.yml`

- Installs tree-sitter dependencies and runs `rag sync --since <base sha>` (falling back to full `rag index`).
- Emits human-readable and JSON stats artifacts (`rag_stats.txt`, `rag_stats.json`) containing estimated remote tokens avoided.
- Uploads artifacts per job for later inspection or cost tracking.

### Editor automation

See `DOCS/SETUP/Editor_Hooks.md` for LazyVim and VS Code snippets that call `scripts/rag_sync.sh`, which in turn drives `rag sync --stdin`. These hooks keep the index warm without manual commands.

### Enrichment / embedding stubs

- `python -m tools.rag.cli enrich --dry-run` emits JSON describing spans missing summaries/tags, including the LLM contract we plan to enforce (`schema_version`, word caps, evidence ranges).
- `python -m tools.rag.cli enrich --execute` runs a deterministic local stub today; swap in Qwen/GPT later without touching the CLI.
- `python -m tools.rag.cli embed --dry-run` lists spans lacking vectors plus the recommended embedding model parameters. Add `--execute` to persist deterministic hash-based vectors (default model `hash-emb-v1`, dim 64) without hitting remote services.

Both commands pivot on `span_hash`, so once the actual workers exist they can safely retry or resume without duplicating effort.

## Next Actions

1. **Broaden span extraction** (Go/Java/C/C++/Rust/etc.) by adding language-specific walkers in `tools/rag/lang.py`.
2. **CI integration:** run `python -m tools.rag.cli sync --since $BASE_SHA` after tests to keep the index warm, then publish stats to build artifacts.
3. **Editor hooks:** ship `:!python -m tools.rag.cli sync --path %` for Neovim and a VS Code task, documenting keybindings in a forthcoming `DOCS/SETUP/Developer_Workflow.md`.
4. **Deterministic agents:** build enrichment/embedding workers that read `.rag/index.db` and write back summaries/tags before escalating to Qwen.

Once these are in place, remote models become the finishing pass rather than the source of truth.
