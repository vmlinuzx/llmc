# REQUIREMENTS: Domain RAG Tech Docs — Phase 1

**SDD Source:** `DOCS/planning/SDD_Domain_RAG_Tech_Docs.md` → Section 7, Phase 1  
**Branch:** `feature/domain-rag-tech-docs`  
**Scope:** Foundation — Index naming + diagnostics only

---

## Objective

Eliminate index collisions and make domain decisions observable during indexing.

---

## Acceptance Criteria

### AC-1: Deterministic Index Naming

**Create `tools/rag/index_naming.py`:**

```python
def resolve_index_name(base: str, repo: str, sharing: str, suffix: str = "") -> str:
    """Resolve final index name based on sharing strategy.
    
    Args:
        base: Base index name (e.g., "emb_tech_docs")
        repo: Repository name (e.g., "llmc")
        sharing: "shared" or "per-repo"
        suffix: Optional deployment suffix
        
    Returns:
        Final index name (e.g., "emb_tech_docs_llmc")
    """
    return base if sharing == "shared" else f"{base}_{repo}{suffix}"
```

**Tests:** `tests/rag/test_index_naming.py`
- `test_shared_mode_returns_base()` — sharing="shared" returns just base
- `test_per_repo_mode_appends_repo()` — sharing="per-repo" returns `{base}_{repo}`
- `test_suffix_appends()` — suffix is appended when provided
- `test_empty_inputs()` — handles empty strings gracefully

---

### AC-2: Structured Diagnostic Logs

**During indexing, emit structured logs:**

```
INFO domain=tech_docs override="DOCS/**" index="emb_tech_docs_llmc" extractor="TechDocsExtractor" chunks=24 ms=712
```

**Required fields:**
- `domain` — Resolved domain type
- `override` — Which path pattern matched (or "extension" or "default")
- `index` — Resolved index name from AC-1
- `extractor` — Which extractor class was used
- `chunks` — Number of chunks produced
- `ms` — Time in milliseconds

**Implementation location:** Modify the indexer to log this line for each file processed.

---

### AC-3: CLI Flag `--show-domain-decisions`

**Add flag to indexer CLI:**

```bash
llmc index --show-domain-decisions
```

**Output format (one line per file):**

```
INFO indexer: file=DOCS/API.md domain=tech_docs reason=path_override:DOCS/**
INFO indexer: file=src/main.py domain=code reason=extension:.py
INFO indexer: file=notes.txt domain=tech_docs reason=default_domain
```

**Reasons enum:**
- `path_override:{pattern}` — Matched a path override pattern
- `extension:{ext}` — Matched by file extension
- `default_domain` — Fell back to default_domain setting
- `global_default` — Fell back to repository.domain

---

### AC-4: Config Schema Extension

**Add to `llmc.toml` schema (can be stubbed for now):**

```toml
[repository]
domain = "code"  # "code" | "tech_docs" | "legal" | "medical" | "mixed"
default_domain = "tech_docs"

[repository.path_overrides]
"DOCS/**" = "tech_docs"
"*.md" = "tech_docs"
"*.py" = "code"
```

**For Phase 1:** Schema can be defined but not fully consumed. Indexer must at least parse and log the values.

---

## Out of Scope (Phase 2+)

- ❌ TechDocsExtractor implementation
- ❌ Domain-specific embedding profiles  
- ❌ Graph extraction
- ❌ MCP resource exposure
- ❌ Hybrid search/reranking

---

## Verification

B-Team must verify:

1. `tools/rag/index_naming.py` exists and has the function
2. `tests/rag/test_index_naming.py` exists with 4+ tests
3. Tests pass: `pytest tests/rag/test_index_naming.py -v`
4. Indexer logs structured output when run
5. `--show-domain-decisions` flag is recognized

---

## Context Files

If you need context on existing code patterns:
- `tools/rag/` — Existing RAG tooling
- `llmc.toml` — Current config format
- `tests/rag/` — Existing test patterns

---

**END OF REQUIREMENTS**
