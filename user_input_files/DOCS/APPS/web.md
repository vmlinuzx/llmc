# Web (apps/web)

Overview
- Minimal Express service that zips the `/template` directory and returns it to the browser. Useful as a lightweight alternative to the Next.js builder.

How to run
- `cd apps/web && npm install`
- `npm start` (defaults to `PORT=4000`)

Routes
- `GET /health` → `{ status: 'ok', templatePath, port }`
- `POST /generate` → `application/zip` stream containing the `/template` directory and a small `selection.json` metadata file.
  - Body: `route=local|api|codex` (form URL‑encoded; defaults to `local`)

Environment
- `PORT` (server port)
- `TEMPLATE_DIR` is resolved to `../../template` relative to `apps/web/server.js` and must exist.

Implementation details
- Uses `archiver` to stream the ZIP and sets `Content-Disposition: attachment; filename="llmc-template-<route>.zip"`.
- Serves static assets from `apps/web/public`.

