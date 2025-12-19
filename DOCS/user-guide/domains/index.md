# Domain Guides

<!-- TODO: Phase 5d will flesh these out -->

LLMC supports different repository types with specialized extraction and search behavior.

---

## Supported Domains

| Domain | Description |
|--------|-------------|
| **Code** | Python, TypeScript, JavaScript, Go, Java |
| **Tech Docs** | API docs, man pages, config references |
| **Medical** | Clinical notes, PHI-safe processing |
| **Mixed** | Repositories with both code and documentation |

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
