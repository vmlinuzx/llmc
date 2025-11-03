# LLMC Template Builder (MVP)

This MVP provides a tiny web interface for packaging the starter workspace into a downloadable zip. It mirrors the Codex routing choices available in `scripts/codex_wrap.sh`.

## Run locally

```bash
cd apps/web
npm install
npm start
```

The server listens on `http://localhost:4000`. Open that URL in a browser to pick the Codex route and download a zip.

## How it works

- **Frontend:** Static HTML form under `apps/web/public/index.html` lists the three routing modes (`local`, `api`, `codex`).
- **Backend:** `apps/web/server.js` streams a zip of the `template/` directory using `archiver`. It also injects a small `selection.json` that records the chosen route and timestamp for traceability.
- **Health check:** `GET /health` returns JSON with the resolved template path and port.

## Template layout (proposed)

```
template/
├── app/
│   ├── api/
│   │   ├── auth/[...nextauth]/route.ts
│   │   └── upload/route.ts
│   └── page.tsx
├── lib/
│   ├── db.ts              # Postgres client
│   ├── auth.ts            # NextAuth config
│   └── files.ts           # File upload helpers
├── prisma/
│   └── schema.prisma      # Or SQL migrations
├── public/
│   └── uploads/           # User files
├── docker-compose.yml     # Postgres + app
├── Dockerfile
├── .env.example
└── README.md
```

Everything stays OSS-friendly: Next.js App Router, Postgres + Prisma, and NextAuth as the baseline stack so the downloaded template is deployable without closed services.

## Next ideas

- Expand the options form with additional `codex_wrap.sh` toggles (auto-commit, sync, etc.).
- Add auth or rate limiting before exposing beyond localhost.
- Generate tailored files inside the archive (e.g., pre-populated `.env.local`).
