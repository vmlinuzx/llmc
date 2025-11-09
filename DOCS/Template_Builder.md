# LLMC Template Builder (MVP)

This MVP ships a Next.js App Router UI for packaging the starter workspace into a downloadable zip. It mirrors the Codex routing choices surfaced through `scripts/codex_wrap.sh`.

## Run locally

```bash
cd apps/template-builder
npm install
npm run dev
```

The dev server listens on `http://localhost:3000`. Open that URL, select a model profile, tools, and artifacts, then click **Generate LLMC Bundle** to download the zip.

## How it works

- **Frontend:** `app/page.tsx` renders the form, fetches dynamic options, and streams the generated bundle to the browser.
- **Registry API:** `app/api/options/route.ts` loads tool, profile, and artifact metadata from the repo via `lib/registry.ts`.
- **Bundle API:** `app/api/generate/route.ts` calls `lib/generateBundle.ts`, which copies the `template/` tree, rewrites `.codex/tools.json` & `.codex/config.toml`, and attaches contracts, agent manifests, and env presets.

## Bundle layout today

The base blueprint under `template/` currently provides shared orchestration config:

```
template/
├── .codex/         # Codex defaults (config + tool registry)
├── .llm/           # Prompt presets + router policy
├── .vscode/        # Recommended editor settings
├── .codexignore    # Files ignored by Codex CLI
└── .gitignore
```

When you generate a bundle the runtime adds:

- `README.md` with next steps and resolved env defaults.
- `manifest.json` capturing the selection metadata.
- `contracts/` if selected (Markdown guardrails tailor-made per tool).
- `agents/` manifests enumerating MCP entry points.
- `envs/.env.llmc` pre-populated with profile + tool settings.

This keeps the MVP focused on orchestration while we land the application scaffold and RAG wiring.

## Next steps

- Seed `template/` with the Next.js + Prisma vertical slice skeleton.
- Include ready-to-run agent entry points alongside the manifests.
- Package RAG automation helpers so bundles can refresh context immediately.
