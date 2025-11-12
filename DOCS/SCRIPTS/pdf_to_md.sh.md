# pdf_to_md.sh — PDF → Markdown Converter

Path
- scripts/pdf_to_md.sh

Purpose
- Convert a PDF to GitHub‑Flavored Markdown and optionally extract embedded media.

Usage
- `scripts/pdf_to_md.sh [--output FILE] [--media-dir DIR] [--no-media] <input.pdf>`

Requirements
- `pandoc` ≥ 2.0 and `pdftohtml` (Poppler) on PATH

Outputs
- Writes `<stem>.md` next to the PDF by default; media under `<stem>_assets/` unless `--no-media` is set.

