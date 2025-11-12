# Local Development Tooling & Usage Patterns

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
- fd may be installed as fdfind on Ubuntu; use `command -v fd || command -v fdfind`.
- yq is the upstream mikefarah release binary.
- perf via linux-tools is optional; use only if kernel tools match.

Usage Patterns (localhost)
- Search (read-only default): `rg --hidden --line-number --iglob '!node_modules' 'TODO|FIXME'`
- Structure overview: `tree -a -I 'node_modules|.git|.venv' -L 2`
- JSON: `jq -r '.items[] | [.name, .version] | @tsv' package-lock.json`
- YAML (in-place): `yq -i '.service.port = 8081' config.yaml`
- Safe diffs: `git diff --patch > /tmp/codex-work/changes.patch`
- Temp worktree apply: `git worktree add -f /tmp/codex-worktree && git -C /tmp/codex-worktree apply patch.patch --3way --check`
- Python venv: `python3 -m venv .venv && . .venv/bin/activate && pip install -U pip`
- C/C++ build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j"$(nproc)"`
- Diagnostics: `timeout 30s strace -f -tt -o /tmp/codex-work/strace.log ./app --help || true`
- Networking: `dig +short api.example.com`; `nc -vz api.example.com 443`

## Visual Web Testing Suite (Playwright + Percy + Sentry + Lighthouse + axe + mitmproxy)

Scope
- Localhost only by default (http://127.0.0.1:PORT). Do not point tools at remote/staging/production unless explicitly requested.
- Purpose: diagnose “page renders but looks wrong/blank” by combining rendering, visual diffs, error capture, perf health, a11y signals, and network inspection.

Cross-cutting Rules
- Timebox: ≤ 5 minutes total per smoke session; ≤ 2 minutes per tool. Use tmux policy (dc-<task>) and tee logs to `/tmp/codex-work/<session>/`.
- Artifacts: write under `artifacts/visual/<tool>/<timestamp>/`; never overwrite existing run data.
- No installs by default. Assume tools are available. If missing, stop and print exact commands; do not install unless Dave says “install X for N minutes”.
- PII/Security: never record Authorization headers, cookies, or POST bodies with secrets. Redact before saving flows/logs.
- Network: prefer 127.0.0.1 over localhost to avoid IPv6/hostname issues.

### Playwright (headless browser)
- Contracted uses: render pages, assert key elements, capture screenshots, save console and network errors.
- Guardrails: headless only; disable video by default; cap navigation timeout 30s; single worker unless asked.
- Common commands:
  - Start dev server per tmux policy (session: dc-nextdev).
  - Ad-hoc capture:
    ```bash
    node -e "(async()=>{const {chromium}=require('playwright');const b=await chromium.launch();const p=await b.newPage();p.on('console',m=>console.error('[console]',m.type(),m.text()));await p.goto('http://127.0.0.1:3001/map',{waitUntil:'load'});await p.screenshot({path:'artifacts/visual/playwright/' + Date.now() + '/map.png', fullPage:true});await b.close();})();"
    ```
  - Tests (when present): `npx playwright test --reporter=line --timeout=30000`.
- Logs: persist browser console and failed request info alongside screenshots.

### Percy (visual regression)
- Contracted uses: snapshot key views to detect rendering/regression differences.
- Env: requires `PERCY_TOKEN` to upload. Without it, run locally and keep artifacts only.
- Example: `PERCY_LOGLEVEL=warn npx percy exec -- npx playwright test -g "@percy"`
- Guardrails: snapshot only public, non-sensitive pages; limit to ≤ 5 snapshots per smoke run.

### Sentry (frontend error tracking)
- Contracted uses: capture client-side errors/breadcrumbs during local sessions.
- Env toggles: `SENTRY_DSN`, `SENTRY_ENV=local`, `SENTRY_DEBUG=1`.
- Default policy: do not send data by default in dev; only enable if `SENTRY_ENABLE_DEV=true`. Sanitize URLs and strip PII.
- When enabled, attach the Sentry console/error log export to `artifacts/visual/sentry/<ts>/events.json`.

### Lighthouse CI (page health)
- Contracted uses: perf/SEO/PWA/accessibility smoke; fail-fast signals.
- Example: `npx lhci autorun --collect.url=http://127.0.0.1:3001/ --collect.url=http://127.0.0.1:3001/map --upload.target=filesystem --upload.outputDir=artifacts/visual/lhci/$(date +%s)`
- Guardrails: run against local dev only; cap to 2 URLs per smoke; no network throttling changes unless asked.

### axe-core (a11y smoke)
- Contracted uses: catch common DOM/render issues (e.g., zero-height canvas, missing ARIA) that often correlate with blank pages.
- Example with Playwright:
  ```bash
  node -e "(async()=>{const {chromium}=require('playwright');const AxeBuilder=require('@axe-core/playwright').default;const b=await chromium.launch();const p=await b.newPage();await p.goto('http://127.0.0.1:3001/map');const rs=await new AxeBuilder({page:p}).analyze();require('fs').mkdirSync('artifacts/visual/axe',{recursive:true});require('fs').writeFileSync('artifacts/visual/axe/results.json',JSON.stringify(rs,null,2));await b.close();})();"
  ```
- Guardrails: treat as advisory; do not block unless user requests gating.

### mitmproxy (network inspection)
- Contracted uses: inspect tile/style requests, CORS/CSP/mixed-content, auth problems.
- Run (localhost only):
  ```bash
  mkdir -p /tmp/codex-work/mitm-map && mitmdump -w /tmp/codex-work/mitm-map/flows.dump --listen-host 127.0.0.1 --listen-port 8081 &
  ```
- Configure Playwright proxy with `{ proxy: { server: 'http://127.0.0.1:8081' } }`.
- Stop when done and save a filtered JSON (`mitmproxy --export` or `mitmdump -ns` script) with secrets redacted.
- Guardrails: localhost domains only by default; never export Authorization headers; limit capture to ≤ 2 minutes.

Exit Criteria for Visual Smoke
- At least one of: valid screenshot with content OR Percy snapshot OR Lighthouse report plus axe results.
- If blank/failed: attach console logs and last 50 network errors, note whether fallback basemap engaged, and list the env that controlled it (`NEXT_PUBLIC_MAP_PROVIDER`/`NEXT_PUBLIC_TILE_STYLE_URL`).
