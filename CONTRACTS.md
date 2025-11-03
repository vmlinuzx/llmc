CONTEXT CONTRACT:
- Environment: Linux. Canonical repo = /home/$USER/src/llmc
- Ingest: read AGENTS.md
- Write: follow instructions in AGENTS.md; avoid editing outside requested sections.
- If AGENTS.md is missing: create a minimal scaffold and stop (no other edits).
- If required markers aren't found: add them to AGENTS.md and stop after confirming with Dave.
- Log: attempt to call agent-memory to record a project memory (file path + short summary). If unavailable, emit a local log line instead; never fail the run due to logging.
- Output: return a unified diff of AGENTS.md and the memory ID. Do not propose moving paths or using /mnt/c.
- UTC format: YYYY-MM-DDTHH:MM:SSZ

# COMPACT OPERATING CONTRACT - No Yak Mode

Context
- Repo: /home/$USER/src/llmc. Stay in repo.
- Default model behavior: minimalist, deterministic, no network, no installs.

Task Protocol
1) Read my ask. Confirm one concrete deliverable (<= ~50 LOC or one doc section).
2) Show a 3-bullet plan. Await my approval or continue if I say 'go' (or wrapper pre-approves).
3) Do it. Change at most one file unless I said otherwise.
4) Validate locally (quick self-check). No extra files or tooling.

Stop Conditions
- Stop immediately when: (a) deliverable is done, (b) blocked by missing info, or (c) timebox feels hit.
- If blocked (missing file/markers), print a BLOCKED report with the exact remediation step, perform no writes, and return NOOP.
- Then print a 5-line summary + next 3 suggested steps. Do not keep going.

Constraints
- Ask before package installs, services, CI, docker, MCP, or scripts.
- Ask before any refactors with prepended WARNING REFACTOR REQUEST. TYPE "ENGAGE" TO CONFIRM, and only do refactor when ENGAGE is typed or selected; otherwise assume no refactors. No renames. No reorganizing. Touch only the target file.
- Be diff-aware: if content is identical, don't write.

Tooling & Install Policy (to avoid multi‑hour installs)
- Default: no network installs. If `ask_for_approval = "never"`, do not install or download anything; only report missing tools and provide copy‑paste commands.
- Timebox: if user explicitly asks to install, hard‑limit any install session to 10 minutes wall clock; stop and report partial results at the limit.
- Scope: only the following tools are allowed to be installed when requested: `node`, `npm`, `jq`, `rg`, `ollama`, `docker`, `psql`, `supabase`, `lynx`, `gh`.
- Fallbacks: when a tool is missing, use these fallbacks instead of installing:
  - supabase → use `psql` for DB tasks; skip project‑scaffold features.
  - lynx → use `curl` for HTTP checks.
  - ollama/LLM → skip; never pull models automatically.
- Vendor path: prefer repo‑local `tools/bin/*` over system PATH (user set `PATH=./tools/bin:$PATH`). Binaries in `tools/bin` must be pinned + checksummed; no silent updates.
- Budget prompts: agent must print what it intends to install, size and time estimates, and wait unless user said "go" in this session.
- CI/devcontainer: recommend using prebuilt image with pinned CLIs; agent must prefer that when present.

Operational Guardrails
- Never apt-get/apt install without explicit user opt‑in.
- Never run install loops or retries silently; max 1 retry per tool.
- Abort any install that exceeds 2 minutes without progress output.

tmux Policy (long-running tasks)
- Any task expected to exceed 2 minutes MUST run inside a named tmux session: `dc-<task>` (e.g., `dc-build`, `dc-tests`, `dc-install`).
- Wrap long tasks with `timeout` and tee logs to `/tmp/codex-work/<session>/run.log`.
- Clean up: detach and kill the tmux session when finished; do not leave background processes.
- No daemonizing inside tmux without explicit approval.
- Example:
  - `mkdir -p /tmp/codex-work/dc-install`
  - `tmux new -s dc-install 'timeout 10m bash -lc "YOUR_CMD |& tee /tmp/codex-work/dc-install/run.log"'`
  - `# Reattach: tmux attach -t dc-install  |  Detach: Ctrl-b d  |  Kill: tmux kill-session -t dc-install`
 - Helper: `scripts/run_in_tmux.sh -s dc-install -T 10m -- "YOUR_CMD"`

Optional Light Log (only if something changed)
- Update DOCS/SESSION_LATEST.md with: Updated:<UTC>, Last actions (<=3 bullets), Next (3 bullets).
- If file absent, create it. If identical, skip writing.

END SESSION
- When I type 'END SESSION': summarize in 6-10 bullets (what changed, open decisions, next).
- No file writes unless I explicitly say 'write docs'.


## Testing Requirements

See AGENTS.md Testing Protocol section for full details.

Summary:
1. Restart affected services
2. Test with lynx (pages) or curl (APIs)
3. Check logs for errors
4. Browser spot check
5. Report results in response

Skip testing for: Docs-only changes, config updates, comments.





### File Encoding

All repository files must be UTF-8 (no BOM) with LF line endings.


## Localhost Tools for Codex (Baseline)

Scope
- Local development machine only (localhost). Do not install or use these on remote servers unless explicitly requested.

Baseline Inventory (expected)
- VCS: git — clone, fetch, status, diff, grep, apply patches. No global config changes.
- HTTP/Fetch: curl, wget — fetch files/JSON, health checks. Use -fsSL/--retry prudently.
- Archives: zip/unzip, tar, xz, gzip, bzip2 — pack/unpack artifacts. Preserve perms (e.g., tar with --numeric-owner when needed).
- Crypto/Certs: gnupg, ca-certificates — verify signatures, import/read keys locally. Never export private keys.
- Core utils: coreutils, findutils, moreutils, tree, rsync — file ops, structured pipelines. Prefer rsync -a --delete for sync.
- Build: build-essential, cmake, pkg-config — compile C/C++ in $WORKDIR/build.
- Python: python3, python3-venv, pip, pipx — run scripts, create venvs. Venv path: .venv in repo.
- Editors/TTY: vim/neovim, nano, tmux, screen — quick edits/sessions. Avoid interactive editors unless requested.
- Inspect/Debug: gdb, strace, ltrace, htop, lsof — diagnose crashes/syscalls/open files. Use -q/-batch and timeouts.
- Text/Data: jq, yq (mikefarah), ripgrep (rg), fd (Ubuntu binary may be fdfind), sed, awk, diffutils, sqlite3 — fast search and transforms. Prefer rg/fd over grep/find.
- Net tools: openssh-client, netcat-traditional, dnsutils (dig), traceroute — SSH/scp to allowed hosts, port/DNS checks. No port listeners without approval.
- Sys utils: htop, btop, tree, rsync, lsof — visibility, structure, sync. Read-only unless syncing workspace.

Notes
- fd may be installed as fdfind on Ubuntu; use command -v fd || command -v fdfind.
- yq is the upstream mikefarah release binary.
- perf via linux-tools is optional; use only if kernel tools match.

Usage Patterns (localhost)
- Search (read-only default): rg --hidden --line-number --iglob '!node_modules' 'TODO|FIXME'
- Structure overview: tree -a -I 'node_modules|.git|.venv' -L 2
- JSON: jq -r '.items[] | [.name, .version] | @tsv' package-lock.json
- YAML (in-place): yq -i '.service.port = 8081' config.yaml
- Safe diffs: git diff --patch > /tmp/codex-work/changes.patch
- Temp worktree apply: git worktree add -f /tmp/codex-worktree && git -C /tmp/codex-worktree apply patch.patch --3way --check
- Python venv: python3 -m venv .venv && . .venv/bin/activate && pip install -U pip
- C/C++ build: cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j"$(nproc)"
- Diagnostics: timeout 30s strace -f -tt -o /tmp/codex-work/strace.log ./app --help || true
- Networking: dig +short api.example.com; nc -vz api.example.com 443

Guardrails & Conventions (localhost)
- Idempotence: prefer commands safe to re-run.
- Dry runs first: use --dry-run/--check or present diffs before mutating.
- No credentials storage: don’t write ~/.ssh, ~/.gitconfig, or global stores.
- Paths: operate within the repo or $WORKDIR; temp files under /tmp/codex-work.
- Large ops: limit breadth (rg -M 2000, tree -L depth) to avoid heavy scans.
- Parallelism: use $(nproc) but cap to ≤ 8 unless explicitly allowed.

Containers & Compose
- Podman may be used for local experiments; prefer Podman unless Docker-specific features are required.
- Docker is available; Compose v2 only when needed and must be called out.


## MCP Tools (optional)

Desktop Commander (if configured)
- Scope: local dev automation — terminal commands, process management, file ops, diff-style editing.
- Guardrails: repo/path allow-list; dry-run diffs before edits; clean up processes; default timeout 10m; no credential exfiltration; logs to /tmp/codex-work/desktop-commander/<task>/.
- Conventions: session names dc-<task>; ripgrep-based search excluding heavy dirs.

Database Toolbox (if configured)
- Scope: standardized tools for SQL/HTTP datasets.
- Guardrails: only declared sources; read-first policy; paramize secrets via env; timeouts/logs to /tmp/codex-work/gcp-toolbox/<task>/.

gcloud CLI (local)
- Scope: read/list/describe by default; mutating actions require explicit plan + rollback + approval.
- Guardrails: project allow-list; ADC only; flag cost-impacting changes.


## MCP Resource Policy
- Prefer MCP resources/templates over ad‑hoc web search.
- Save MCP outputs to /tmp/codex-work/<server>/<task>/ and sanitize logs.
- Read-first: gather schema/info before any mutating action.
- Cost & approval: any non‑trivial cost requires explicit note and rollback/verification steps.


## Visual Web Testing Suite (Playwright + Percy + Sentry + Lighthouse + axe + mitmproxy)

Scope
- Localhost only by default (http://127.0.0.1:PORT). Do not point tools at remote/staging/production unless explicitly requested.
- Purpose: diagnose “page renders but looks wrong/blank” by combining rendering, visual diffs, error capture, perf health, a11y signals, and network inspection.

Cross‑cutting Rules
- Timebox: ≤ 5 minutes total per smoke session; ≤ 2 minutes per tool. Use tmux policy (dc-<task>) and tee logs to /tmp/codex-work/<session>/.
- Artifacts: write under artifacts/visual/<tool>/<timestamp>/; never overwrite existing run data.
- No installs by default. Assume tools are available. If missing, stop and print exact commands; do not install unless Dave says “install X for N minutes”.
- PII/Security: never record Authorization headers, cookies, or POST bodies with secrets. Redact before saving flows/logs.
- Network: prefer 127.0.0.1 over localhost to avoid IPv6/hostname issues.

Playwright (headless browser)
- Contracted uses: render pages, assert key elements, capture screenshots, save console and network errors.
- Guardrails: headless only; disable video by default; cap navigation timeout 30s; single worker unless asked.
- Common commands:
  - Start dev server per tmux policy (session: dc-nextdev).
  - Ad‑hoc capture:
    - `node -e "(async()=>{const {chromium}=require('playwright');const b=await chromium.launch();const p=await b.newPage();p.on('console',m=>console.error('[console]',m.type(),m.text()));await p.goto('http://127.0.0.1:3001/map',{waitUntil:'load'});await p.screenshot({path:'artifacts/visual/playwright/$(date +%s)/map.png', fullPage:true});await b.close();})();"`
  - Tests (when present): `npx playwright test --reporter=line --timeout=30000`.
- Logs: persist browser console and failed request info alongside screenshots.

Percy (visual regression)
- Contracted uses: snapshot key views to detect rendering/regression differences.
- Env: requires `PERCY_TOKEN` to upload. Without it, run locally and keep artifacts only.
- Example:
  - `PERCY_LOGLEVEL=warn npx percy exec -- npx playwright test -g "@percy"` (tests tagged for Percy).
- Guardrails: snapshot only public, non‑sensitive pages; limit to ≤ 5 snapshots per smoke run.

Sentry (frontend error tracking)
- Contracted uses: capture client‑side errors/breadcrumbs during local sessions.
- Env toggles: `SENTRY_DSN`, `SENTRY_ENV=local`, `SENTRY_DEBUG=1`.
- Default policy: do not send data by default in dev; only enable if `SENTRY_ENABLE_DEV=true`. Sanitize URLs and strip PII.
- When enabled, attach the Sentry console/error log export to artifacts `artifacts/visual/sentry/<ts>/events.json`.

Lighthouse CI (page health)
- Contracted uses: perf/SEO/PWA/accessibility smoke; fail‑fast signals.
- Example:
  - `npx lhci autorun --collect.url=http://127.0.0.1:3001/ --collect.url=http://127.0.0.1:3001/map --upload.target=filesystem --upload.outputDir=artifacts/visual/lhci/$(date +%s)`
- Guardrails: run against local dev only; cap to 2 URLs per smoke; no network throttling changes unless asked.

axe-core (a11y smoke)
- Contracted uses: catch common DOM/render issues (e.g., zero‑height canvas, missing ARIA) that often correlate with blank pages.
- With Playwright:
  - `node -e "(async()=>{const {chromium}=require('playwright');const AxeBuilder=require('@axe-core/playwright').default;const b=await chromium.launch();const p=await b.newPage();await p.goto('http://127.0.0.1:3001/map');const rs=await new AxeBuilder({page:p}).analyze();require('fs').mkdirSync('artifacts/visual/axe',{recursive:true});require('fs').writeFileSync('artifacts/visual/axe/results.json',JSON.stringify(rs,null,2));await b.close();})();"`
- Guardrails: treat as advisory; do not block unless user requests gating.

mitmproxy (network inspection)
- Contracted uses: inspect tile/style requests, CORS/CSP/mixed‑content, auth problems.
- Run (localhost only):
  - `mkdir -p /tmp/codex-work/mitm-map && mitmdump -w /tmp/codex-work/mitm-map/flows.dump --listen-host 127.0.0.1 --listen-port 8081 &`
  - Configure Playwright proxy: launch browser with `{ proxy: { server: 'http://127.0.0.1:8081' } }`.
  - Stop when done and save a filtered JSON (`mitmproxy --export` or `mitmdump -ns` script) with secrets redacted.
- Guardrails: localhost domains only by default; never export Authorization headers; limit capture to ≤ 2 minutes.

Exit Criteria for Visual Smoke
- At least one of: valid screenshot with content OR Percy snapshot OR Lighthouse report + axe results.
- If blank/failed: attach console logs and last 50 network errors, note whether fallback basemap engaged, and list the env that controlled it (NEXT_PUBLIC_MAP_PROVIDER/NEXT_PUBLIC_TILE_STYLE_URL).
