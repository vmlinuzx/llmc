# SDD: Document Sidecar System

**Status:** 🟢 Ready for Implementation  
**Priority:** P1  
**Created:** 2025-12-21  
**Estimated Effort:** 8-12 hours  
**Difficulty:** 🟡 Medium

---

## 1. Problem Statement

Binary and semi-structured document formats are terrible for RAG:

| Format | Issues |
|--------|--------|
| **PDF** | Layout destroys reading order, tables become gibberish, chunking splits sentences |
| **DOCX** | XML soup, lossy extraction, formatting artifacts |
| **RTF** | Ancient format, no good tooling |
| **PPTX** | Slides become meaningless fragments |
| **EPUB** | Actually okay (HTML inside), but needs unpacking |

**The Result:**
- Users report "it couldn't find X that's clearly in the PDF"
- Embeddings on extracted PDF text are noisy
- Chunk boundaries split semantic units arbitrarily
- Zero heading/section awareness

**Current State:**
- LLMC indexes `.md`, `.py`, `.js`, etc. beautifully
- `TechDocsExtractor` produces heading-aware, anchor-stable chunks for markdown
- PDFs and other binary formats are **completely ignored**

---

## 2. Goals

### 2.1 Primary Goals

1. **Transparent conversion** — binary docs → gzipped markdown sidecars
2. **Search shows original** — results report `docs/spec.pdf:page15`, not sidecar path
3. **Staleness detection** — re-convert only when source changes
4. **Minimal footprint** — gzipped sidecars are ~1-5% of original size
5. **Leverage existing pipeline** — sidecars go through `TechDocsExtractor` → enrichment → search

### 2.2 Non-Goals (Phase 1)

- VLM-based extraction (tables, diagrams → descriptions) — Phase 2
- Per-page image extraction for layout-heavy docs — Phase 2
- Custom PDF parser — use existing tools (pymupdf, pdfplumber, marker)

---

## 3. Architecture

### 3.1 Directory Structure

```
repo/
├── docs/
│   ├── spec.pdf                     # 500KB original
│   ├── guide.docx                   # 200KB original
│   └── notes.md                     # Native markdown (indexed directly)
│
└── .llmc/
    └── sidecars/
        └── docs/
            ├── spec.pdf.md.gz       # ~5KB gzipped markdown
            └── guide.docx.md.gz     # ~3KB gzipped markdown
```

### 3.2 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INDEXER                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. Indexer encounters docs/spec.pdf                                    │
│                                                                          │
│   2. Check sidecar freshness:                                            │
│      - Sidecar exists? Check source mtime vs sidecar mtime               │
│      - Stale or missing? Generate new sidecar                            │
│                                                                          │
│   3. Convert: pdf → markdown → gzip → .llmc/sidecars/docs/spec.pdf.md.gz│
│                                                                          │
│   4. Index the SIDECAR using TechDocsExtractor                           │
│      - Heading-aware chunking                                            │
│      - Anchor-stable spans                                               │
│                                                                          │
│   5. Store spans with ORIGINAL path (docs/spec.pdf)                      │
│      - files.path = "docs/spec.pdf"                                      │
│      - files.sidecar_path = ".llmc/sidecars/docs/spec.pdf.md.gz"         │
│                                                                          │
│   6. Search results show "docs/spec.pdf:L42" but read from sidecar       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Supported Formats (Phase 1)

| Extension | Converter | Notes |
|-----------|-----------|-------|
| `.pdf` | `pymupdf` (fitz) | Fast, reliable, handles most PDFs |
| `.docx` | `python-docx` + custom | Preserve headings, lists, tables |
| `.pptx` | `python-pptx` + custom | Slide-per-section, speaker notes |
| `.rtf` | `striprtf` | Simple, lossy but functional |

### 3.4 Conversion Pipeline

```python
class SidecarConverter:
    """Converts binary documents to markdown sidecars."""
    
    CONVERTERS = {
        '.pdf': PdfToMarkdown,
        '.docx': DocxToMarkdown,
        '.pptx': PptxToMarkdown,
        '.rtf': RtfToMarkdown,
    }
    
    def convert(self, source_path: Path, repo_root: Path) -> Path | None:
        """Convert source to gzipped markdown sidecar.
        
        Returns:
            Path to sidecar if successful, None if format unsupported
        """
        ext = source_path.suffix.lower()
        if ext not in self.CONVERTERS:
            return None
            
        converter = self.CONVERTERS[ext]()
        markdown = converter.convert(source_path)
        
        sidecar_path = self._sidecar_path(source_path, repo_root)
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        
        with gzip.open(sidecar_path, 'wt', encoding='utf-8') as f:
            f.write(markdown)
            
        return sidecar_path
    
    def _sidecar_path(self, source: Path, repo_root: Path) -> Path:
        """Compute sidecar path: .llmc/sidecars/<rel_path>.md.gz"""
        rel = source.relative_to(repo_root)
        return repo_root / ".llmc" / "sidecars" / f"{rel}.md.gz"
```

---

## 4. Database Changes

### 4.1 Schema Migration

Add `sidecar_path` column to `files` table:

```sql
ALTER TABLE files ADD COLUMN sidecar_path TEXT;
```

**Semantics:**
- `NULL` → native file, indexed directly
- Non-NULL → binary file, sidecar contains indexed content

### 4.2 Query Patterns

**Indexing:**
```sql
INSERT INTO files (path, sidecar_path, ...) 
VALUES ('docs/spec.pdf', '.llmc/sidecars/docs/spec.pdf.md.gz', ...);
```

**Search results:**
```sql
SELECT path, sidecar_path FROM files WHERE id = ?;
-- Display: path (docs/spec.pdf)
-- Read content: sidecar_path if non-null, else path
```

---

## 5. Lifecycle Management (Critical)

The sidecar system must handle file changes correctly. The existing infrastructure already supports this — we just need to hook in.

### 5.1 Existing Infrastructure

| Event | What Happens Now | Location |
|-------|------------------|----------|
| **File Modified** | `sync_paths` detects via mtime/hash, re-indexes | `indexer.py:sync_paths` |
| **File Deleted** | `db.delete_file(path)` removes from DB, CASCADE deletes spans | `indexer.py:sync_paths` |
| **File Created** | Picked up by next index sweep or watcher | `watcher.py` → `service.py` |

### 5.2 Sidecar Lifecycle Hooks

#### On Source File Modification

```python
# In sync_paths / index_repo, after detecting file change:
if is_sidecar_eligible(ext):
    sidecar_path = sidecar_converter.convert(source_path, repo_root)
    # Sidecar is regenerated, then indexed normally
```

**Trigger:** `source.mtime > sidecar.mtime` OR source hash changed

#### On Source File Deletion

```python
# In sync_paths, when file no longer exists:
if not absolute.exists():
    # Already happens:
    db.delete_file(rel)
    
    # NEW: Also remove orphaned sidecar
    sidecar_path = sidecar_converter.get_sidecar_path(rel, repo_root)
    if sidecar_path.exists():
        sidecar_path.unlink()
        log.info(f"Removed orphan sidecar: {sidecar_path}")
```

#### Periodic Orphan Cleanup

Sidecars can become orphaned if:
- Source was deleted while service was stopped
- Manual deletion of source file
- Source renamed (old sidecar remains)

```python
def cleanup_orphan_sidecars(repo_root: Path) -> int:
    """Remove sidecars whose source files no longer exist.
    
    Returns:
        Number of orphaned sidecars removed
    """
    sidecars_dir = repo_root / ".llmc" / "sidecars"
    if not sidecars_dir.exists():
        return 0
    
    removed = 0
    for sidecar in sidecars_dir.rglob("*.md.gz"):
        # Reconstruct source path from sidecar path
        rel_sidecar = sidecar.relative_to(sidecars_dir)
        source_rel = str(rel_sidecar).removesuffix(".md.gz")
        source_path = repo_root / source_rel
        
        if not source_path.exists():
            sidecar.unlink()
            removed += 1
            log.info(f"Removed orphan: {sidecar}")
    
    return removed
```

**When to run:**
- `llmc sidecar clean` (manual)
- On service startup with `LLMC_SIDECAR_CLEANUP=1`
- Optionally during vacuum cycles

### 5.3 Integration Points

| Component | Change Required |
|-----------|-----------------|
| `indexer.py:sync_paths` | Delete sidecar when source deleted |
| `indexer.py:index_repo` | Generate sidecar before extraction |
| `service.py:RAGService` | Optional orphan cleanup on startup |
| `sidecar.py` | New `cleanup_orphan_sidecars()` function |
| `commands/sidecar.py` | New `llmc sidecar clean` command |

### 5.4 Edge Cases

| Scenario | Behavior |
|----------|----------|
| Source renamed | Old sidecar becomes orphan → cleaned up by `sidecar clean` |
| Source moved to different dir | Same as rename → orphan cleanup handles it |
| Sidecar manually deleted | Regenerated on next index |  
| Service crash mid-conversion | Partial/corrupt sidecar → overwritten on next index |
| Read-only repo | Skip sidecar generation, log warning |

### 5.5 Freshness Check Algorithm

```python
def is_sidecar_stale(source: Path, repo_root: Path) -> bool:
    """Check if sidecar needs regeneration."""
    sidecar = get_sidecar_path(source, repo_root)
    
    if not sidecar.exists():
        return True  # Missing = stale
    
    # mtime comparison
    if source.stat().st_mtime > sidecar.stat().st_mtime:
        return True
    
    return False
```

## 6. Implementation Phases

### Phase 1: Core Sidecar Infrastructure (4-6 hours)

1. **Create `llmc/rag/sidecar.py`:**
   - `SidecarConverter` class with pluggable converters
   - `PdfToMarkdown` using pymupdf
   - Freshness check: `source.mtime > sidecar.mtime`
   - Gzip compression on write

2. **Update `llmc/rag/indexer.py`:**
   - Detect sidecar-eligible files by extension
   - Generate sidecar if stale/missing
   - Pass sidecar content to `TechDocsExtractor`
   - Store original path in `files.path`, sidecar in `files.sidecar_path`

3. **Database migration:**
   - Add `sidecar_path` column
   - Update `Database._run_migrations()`

4. **Update `mcgrep` / search tools:**
   - Display original path, not sidecar
   - Read content from sidecar when present

### Phase 2: Additional Formats (2-4 hours)

1. **Add `DocxToMarkdown`:**
   - Use `python-docx` for extraction
   - Preserve heading levels, lists, tables

2. **Add `PptxToMarkdown`:**
   - Use `python-pptx`
   - One section per slide
   - Include speaker notes

3. **Add `RtfToMarkdown`:**
   - Use `striprtf` for basic conversion

### Phase 3: Polish (2-4 hours)

1. **CLI commands:**
   - `llmc sidecar generate docs/` — force regenerate sidecars
   - `llmc sidecar list` — show all sidecars and freshness
   - `llmc sidecar clean` — remove orphaned sidecars

2. **Stats integration:**
   - `llmc rag stats` shows sidecar count
   - `IndexStats.sidecars` property (already in schema!)

3. **Documentation:**
   - Update AGENTS.md with sidecar-aware search tips
   - Add to CHANGELOG

---

## 7. Converters

### 6.1 PdfToMarkdown

```python
class PdfToMarkdown:
    """Convert PDF to markdown using PyMuPDF."""
    
    def convert(self, path: Path) -> str:
        import fitz  # pymupdf
        
        doc = fitz.open(path)
        lines = []
        
        for page_num, page in enumerate(doc, 1):
            # Add page marker as heading
            lines.append(f"\n## Page {page_num}\n")
            
            # Extract text blocks (preserves reading order better than raw text)
            blocks = page.get_text("blocks")
            for block in blocks:
                text = block[4].strip()
                if text:
                    lines.append(text + "\n")
        
        doc.close()
        return "\n".join(lines)
```

### 6.2 DocxToMarkdown

```python
class DocxToMarkdown:
    """Convert DOCX to markdown preserving structure."""
    
    def convert(self, path: Path) -> str:
        from docx import Document
        
        doc = Document(path)
        lines = []
        
        for para in doc.paragraphs:
            style = para.style.name.lower()
            text = para.text.strip()
            
            if not text:
                continue
                
            # Convert headings
            if "heading 1" in style:
                lines.append(f"# {text}\n")
            elif "heading 2" in style:
                lines.append(f"## {text}\n")
            elif "heading 3" in style:
                lines.append(f"### {text}\n")
            else:
                lines.append(f"{text}\n")
        
        return "\n".join(lines)
```

---

## 8. Test Plan

### 7.1 Unit Tests

```python
def test_pdf_sidecar_generation():
    """Test PDF → markdown sidecar creation."""
    converter = SidecarConverter()
    sidecar = converter.convert(sample_pdf, repo_root)
    assert sidecar.suffix == ".gz"
    assert sidecar.exists()
    
    with gzip.open(sidecar, 'rt') as f:
        content = f.read()
    assert "## Page 1" in content

def test_sidecar_freshness():
    """Test stale sidecar detection."""
    # Create sidecar
    converter = SidecarConverter()
    sidecar = converter.convert(sample_pdf, repo_root)
    
    # Touch source file
    sample_pdf.touch()
    
    # Should detect as stale
    assert converter.is_stale(sample_pdf, repo_root)

def test_search_shows_original_path():
    """Test that search results show PDF path, not sidecar."""
    # Index a PDF
    index_repo()
    
    # Search
    results = search("authentication")
    
    # Should show docs/spec.pdf, not .llmc/sidecars/...
    assert any(r.path == "docs/spec.pdf" for r in results)
```

### 7.2 Integration Tests

```bash
# Create test PDF
echo "Hello World" | enscript -o - | ps2pdf - /tmp/test.pdf

# Generate sidecar
python3 -m llmc.rag.sidecar generate /tmp/test.pdf

# Verify sidecar exists
ls -la .llmc/sidecars/tmp/test.pdf.md.gz

# Index and search
llmc rag index --path /tmp/test.pdf
mcgrep "Hello World"  # Should find in test.pdf
```

---

## 9. Dependencies

### 8.1 Required (Phase 1)

```toml
[project.optional-dependencies]
sidecar = [
    "pymupdf>=1.23.0",  # PDF extraction
]
```

### 8.2 Optional (Phase 2)

```toml
[project.optional-dependencies]
sidecar-full = [
    "pymupdf>=1.23.0",
    "python-docx>=1.0.0",   # DOCX extraction
    "python-pptx>=0.6.21",  # PPTX extraction  
    "striprtf>=0.0.26",     # RTF extraction
]
```

---

## 10. Configuration

```toml
# llmc.toml
[sidecar]
enabled = true
formats = ["pdf", "docx"]  # Which formats to convert
compression = "gzip"       # gzip or none
max_file_size_mb = 50      # Skip huge files
```

---

## 11. Future Work (Phase 2+)

1. **VLM extraction for complex PDFs:**
   - Send page images to Qwen-VL or similar
   - Extract table structure, diagram descriptions
   - Annotate markdown with `<!-- VLM: table showing... -->`

2. **Per-page image fallback:**
   - For layout-heavy docs where text extraction fails
   - Store page images in sidecar directory
   - Reference from markdown: `![Page 5](page_005.png)`

3. **Citation-stable page references:**
   - Graph edges include page numbers
   - `docs/spec.pdf:page15` as stable citation

4. **Incremental page updates:**
   - Only re-extract changed pages
   - Requires page-level hashing

---

## 12. Rollback Plan

1. **Database:** `sidecar_path` column is nullable, ignored by existing code
2. **Sidecars:** `.llmc/sidecars/` can be deleted without affecting core index
3. **Dependencies:** pymupdf is optional, fallback is "skip binary files"

No breaking changes to existing functionality.

---

## 13. Approval

- [ ] Dave reviews and approves
- [ ] Implementation begins

---

## Appendix A: Why Sidecars?

**Alternative 1: Direct PDF chunking**
- Loses structure
- Noisy embeddings
- Inconsistent chunk boundaries
- ❌ Rejected

**Alternative 2: Store markdown in DB**
- Larger database
- No file-based tooling
- Can't `cat` the sidecar for debugging
- ❌ Rejected

**Alternative 3: Sidecars (chosen)**
- Mirrors repo structure
- Gzipped for minimal footprint
- Standard markdown tooling works
- Easy to debug (`zcat sidecar.md.gz`)
- Works with existing TechDocsExtractor
- ✅ Accepted

---

## Appendix B: Size Estimates

| Original | Sidecar | Compression |
|----------|---------|-------------|
| 500KB PDF | ~15KB .md | ~5KB .md.gz |
| 1MB PDF | ~30KB .md | ~10KB .md.gz |
| 200KB DOCX | ~8KB .md | ~3KB .md.gz |

**Typical compression: 95-99% size reduction**
