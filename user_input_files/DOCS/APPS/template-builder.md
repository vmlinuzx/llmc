# Template Builder (apps/template-builder)

Overview
- Next.js 14 App Router application that lets a user pick a model profile, tools, and artifact set, and then downloads a ready-to-unzip LLMC bundle built from `/template`.
- Exposes two API routes under `/api/*` and a simple landing page with a Generate button.

How to run
- `cd apps/template-builder && npm install`
- `npm run dev` (port printed by Next)
- Build/start: `npm run build && npm run start`
- Tests: unit `npm test` (Jest), e2e `npm run test:e2e` (Playwright)

Key scripts
- `dev`, `build`, `start`, `lint`, `test`, `test:e2e` (see package.json)

Directory structure (selected)
- `app/` — App Router entrypoints
  - `layout.tsx`, `globals.css`
  - `page.tsx` — UI; fetches options and posts to `/api/generate`
  - `api/options/route.ts` — GET → template registry JSON
  - `api/generate/route.ts` — POST → returns a ZIP with the generated bundle
- `lib/` — bundle logic
  - `generateBundle.ts` — core `createBundle()` implementation
  - `registry.ts`, `options.ts` — available tools, artifacts, and model profiles
- `tests/` — Jest unit + Playwright e2e

API
- `GET /api/options` → returns the current template registry (tools, artifacts, model profiles, env defaults).
- `POST /api/generate` (JSON body)
  - Request: `{ projectName: string, profile: string, tools: string[], artifacts: string[] }`
  - Response: `application/zip` with headers `Content-Disposition: attachment; filename="<slug>-bundle.zip"` and `x-download-filename`.
  - Defaults: if `tools` or `artifacts` omitted, uses `defaultSelected` or falls back to “all available”.

Bundle contents (created by `createBundle`)
- Entire `/template` directory (recursively)
- `README.md` — quick start and environment preview
- `manifest.json` — machine-readable selection summary
- Optional artifacts (if selected):
  - `contracts/orchestration.md` — generated based on selected tools
  - `agents/*.json` — agent manifests per tool
  - `envs/.env.llmc` — merged env defaults for selected tools and profile
- Patch-ups:
  - `.codex/tools.json` — pruned to selected MCP servers; populates Ollama profiles
  - `.codex/config.toml` — ensures consistent profile defaults

Environment
- Uses `process.env.LLMC_PROJECT_ROOT` (defaults to repo root via `../../`) to resolve `/template`.
- `LLMC_TEMPLATE_ROOT` can override the template root directory.

Notes
- Validation errors (unknown tool/profile/artifact) return `400` with a message.
- The generated ZIP is built with `jszip` entirely in-memory.

