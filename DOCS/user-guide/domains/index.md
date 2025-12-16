# Domain Guides

<!-- TODO: Phase 5d will flesh these out -->

LLMC supports different repository types with specialized extraction and search behavior.

---

## Supported Domains

| Domain | Description | Guide |
|--------|-------------|-------|
| **Code** | Python, TypeScript, JavaScript, Go, Java | [Code Repos](code-repos.md) |
| **Tech Docs** | API docs, man pages, config references | [Tech Docs](tech-docs.md) |
| **Medical** | Clinical notes, PHI-safe processing | [Medical RAG](medical-rag.md) |
| **Mixed** | Repositories with both code and documentation | [Mixed Repos](mixed-repos.md) |

---

## Configuration

Set your domain in `llmc.toml`:

```toml
[repository]
domain = "code"  # or "tech_docs", "medical", "mixed"
```

---

## Auto-Detection

LLMC can auto-detect domain based on file composition:
- Majority `.py`, `.ts`, `.js`, `.go`, `.java` → `code`
- Majority `.md`, `.rst`, `.txt` → `tech_docs`
- Presence of clinical patterns → prompts for `medical`
