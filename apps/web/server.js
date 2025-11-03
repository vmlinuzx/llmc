const express = require('express');
const path = require('path');
const fs = require('fs');
const archiver = require('archiver');

const app = express();
const PORT = process.env.PORT || 4000;
const TEMPLATE_DIR = path.resolve(__dirname, '../../template');
const VALID_ROUTES = new Set(['local', 'api', 'codex']);

if (!fs.existsSync(TEMPLATE_DIR)) {
  console.error(`Template directory not found: ${TEMPLATE_DIR}`);
  process.exit(1);
}

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', templatePath: TEMPLATE_DIR, port: PORT });
});

app.post('/generate', (req, res) => {
  const selectedRoute = (req.body.route || 'local').toLowerCase();

  if (!VALID_ROUTES.has(selectedRoute)) {
    return res.status(400).send('Invalid route selection.');
  }

  const archive = archiver('zip', { zlib: { level: 9 } });

  res.setHeader('Content-Type', 'application/zip');
  res.setHeader(
    'Content-Disposition',
    `attachment; filename="llmc-template-${selectedRoute}.zip"`
  );

  archive.on('error', (err) => {
    console.error('Archive error:', err);
    if (!res.headersSent) {
      res.status(500).send('Failed to build archive.');
    } else {
      res.end();
    }
  });

  archive.pipe(res);

  archive.directory(TEMPLATE_DIR, false);

  const metadata = {
    selectedRoute,
    generatedAt: new Date().toISOString(),
    sourceTemplate: path.relative(process.cwd(), TEMPLATE_DIR),
  };

  archive.append(JSON.stringify(metadata, null, 2), { name: 'selection.json' });

  archive.finalize().catch((err) => {
    console.error('Finalize error:', err);
  });
});

app.listen(PORT, () => {
  console.log(`LLMC template builder listening on http://localhost:${PORT}`);
});
