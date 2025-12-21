# LLMC Roadmap

This roadmap focuses only on **active** work. Completed items are in `ROADMAP_COMPLETED.md`.

- **Now** – Current focus for work sessions
- **Next** – Post-launch improvements
- **Later** – Deeper refactors and R&D

---

## 1. Now (P0 / P1)

### 1.1 CLI Startup Performance (P1)

**Status:** 🟡 Not started  
**Added:** 2025-12-17

**Problem:** `llmc --help` takes several seconds due to eager imports of heavy ML libraries.

**Root Cause:** Top-level imports of `transformers`, `torch`, `sentence_transformers`, `sklearn`, `scipy`, `numpy`.

**Fix:** Move heavy imports inside command functions (lazy loading).

**Effort:** 4-6 hours | **Difficulty:** 🟢 Easy

---

### 1.2 File-Level Descriptions

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Priority:** Medium  

Implemented file-level enrichment that generates ~50 word descriptions of each file's purpose.

**What was built:**
- `llmc debug file-descriptions` CLI command with `--mode cheap|rich` and `--force`
- Intelligent span prioritization: classes > modules > top-level functions
- Staleness tracking via `input_hash` - only recomputes when content changes
- `mcgrep` now shows real file descriptions, falls back to span proxy if none

**Run:** `llmc debug file-descriptions --force` to populate for existing repos.

**Effort:** ~4 hours | **Difficulty:** 🟢 Easy (simpler than estimated)

---

### 1.4 Context-Efficient Inspect (P1) 🔥

**Status:** 🟡 Planned  
**Added:** 2025-12-21  
**Source:** Codex feedback — `inspect --full` consumed 10% of context window for a "what is this repo" question

**Problem:** Current `mcinspect --full` dumps entire file contents. For quick orientation questions, most of that context is noise.

**Proposed Fixes:**

1. **Default to summary mode** — No `--full` by default:
   - Symbol name + kind + file path
   - Summary (from enrichment)
   - Top 3 callers/callees (from graph)
   - Line count + byte size

2. **Add `--capsule` mode** — 5-10 line architecture summary:
   - Purpose (file description)
   - Key exports (symbols)
   - Who depends on this? (top edges)
   - No code dumps

3. **Surface graph edges in default output** — Show callers/callees inline:
   ```
   EnrichmentPipeline (class, llmc/rag/enrichment_pipeline.py:45)
   "Orchestrates batch LLM enrichment with backend cascade"
   Called by: service.run(), workers.execute_enrichment()
   Calls: Database.write_enrichment(), backend.generate()
   ```

**The Goal:** Answer "what does X do?" in ~50 tokens, not 5000.

**Effort:** 3-4 hours | **Difficulty:** 🟢 Easy

---

### 1.3 Security Polish (P2)

**Remaining from 2025-12-17 audit:**

| Priority | Issue | Location | Risk |
|----------|-------|----------|------|
| **P2** | `os.chdir()` in RAG tools | `llmc_mcp/tools/rag.py` | MEDIUM - race conditions |
| **P2** | Unvalidated `repo_root` in RAG | `llmc_mcp/tools/rag.py` | MEDIUM - no `allowed_roots` check |

**📄 Full Report:** `tests/REPORTS/current/rem_mcp_2025-12-17.md`

---

## 2. Next (P1)

Things that make LLMC nicer to live with.

### 2.1 Integrated Graph-Enriched Search

**Status:** 🟡 Planned  
**Added:** 2025-12-19

**Goal:** Elevate rich schema-backed search from `llmc-rag-nav` into `llmc analytics search`.

**Current State:**
- `llmc analytics search` (vector-only) returns paths and snippets without context
- `llmc-rag-nav search` (hidden gem) provides AI summaries, usage examples, type metadata

**The Plan:**
1. Unify search to use `nav_search` logic when graph is available
2. Schema 3.0: Normalize edge semantics, add evidence (file:line), importance ranking
3. UX: `--rich/--plain` toggle

**Effort:** 6-8 hours | **Difficulty:** 🟢 Easy

---

### 2.2 Thin CLI Wrappers for MCP Tools (P1) 🎯

**Status:** 🟡 Planned  
**Added:** 2025-12-19

**Goal:** Create dead-simple CLI wrappers for MCP tools, enriched with schema graph data where useful.

**The Bigger Picture:**
These CLIs serve *two* purposes:
1. **Human/LLM UX:** Simple tools for common tasks
2. **Training Data:** OpenAI-format tool calling patterns for fine-tuning local models

```
mc* CLI Input/Output  →  OpenAI Tool Schemas  →  LLM Training Data
```

Each CLI is a *demonstration* of correct tool usage. Run `mcgrep "router"` → generates an example of `{"name": "rag_search", "arguments": {"query": "router"}}` with expected output. This becomes training data for teaching models how to use LLMC tools natively.

**The Pattern:**
| CLI | MCP Tool | OpenAI Schema | Status |
|-----|----------|---------------|--------|
| `mcgrep` | `rag_search` | `{"name": "rag_search", ...}` | ✅ DONE |
| `mcwho` | `rag_where_used` | `{"name": "rag_where_used", ...}` | ✅ DONE |
| `mcinspect` | `inspect` | `{"name": "inspect", ...}` | 🟡 Planned |
| `mcread` | `read_file` | `{"name": "read_file", ...}` | 🟡 Planned |
| `mcrun` | `run_cmd` | `{"name": "run_cmd", ...}` | 🟡 Planned |

**Graph Enrichment:**
| Tool | Enhancement |
|------|-------------|
| `read_file` | "Related: 3 callers, 5 imports" header |
| `inspect` | Graph neighbor hints |
| `list_dir` | Connectivity ranking |

**Training Data Generation (Future):**
1. `mcgrep --emit-training` → outputs OpenAI tool call + response JSON
2. Collect corpus of tool usage patterns across repos
3. Fine-tune local models (Qwen, Llama) on LLMC-specific tool calling
4. Models learn: "when user asks X, call tool Y with args Z"

**Why This Matters:**
- No MCP required - models learn tool patterns directly
- Training data is generated from *actual* LLMC usage
- Graph enrichment teaches models to chain tools intelligently
- Fine-tuned models > prompt engineering for tool usage

**Implementation:**
1. Start with `mcinspect` (existing `llmc analytics inspect` is buried)
2. Add `mcread` with graph header
3. Add `--emit-training` flag for training data generation

**Effort:** 12-16 hours (CLIs) + 8-12 hours (training emit) | **Difficulty:** 🟢 Easy → 🟡 Medium

**📄 Reference:** `llmc/mcgrep.py`, `llmc/mcwho.py` for patterns

---

### 2.3 AGENTS.md: OpenAI Tool Calling Convention (P1)

**Status:** 🔴 Blocked (depends on 2.2)  
**Added:** 2025-12-19

**Goal:** Update AGENTS.md to tell LLMs to use OpenAI-standard tool calling with the `mc*` CLIs.

**The Insight:**
LLMs have been trained *relentlessly* on OpenAI function calling format. If LLMC tools follow that format:
- **Zero learning curve** - models already know the pattern
- **Minimal context** - no need to dump 10KB of tool schemas
- **Same training pattern** works for MCP, CLI, or fine-tuning

**Before (Expensive):**
```markdown
## Tools
Here are 30 tools with their schemas...
[10KB of JSON definitions]
```

**After (Cheap):**
```markdown
## Tools
Use OpenAI-standard tool calling. Available locally:
- `mcgrep <query>` - semantic code search (rag_search)
- `mcwho <symbol>` - find callers/callees (rag_where_used)
- `mcread <file>` - read file with graph context (read_file)
```

**Why This Works:**
1. Models know `{"name": "...", "arguments": {...}}` format from training
2. Just tell them the tool names → they infer the schema
3. Graph-enriched outputs teach correct tool chaining
4. **Same instructions work for MCP, CLI, or local execution**

**Prerequisite:** Section 2.2 must be complete first (need the CLIs to exist)

**Changes to AGENTS.md:**
- Add section: "OpenAI Tool Calling Convention"
- List `mc*` tools with their MCP equivalents
- Remove verbose schema dumps
- Keep RAG-first contract, but simplify tool docs

**Effort:** 2-4 hours | **Difficulty:** 🟢 Easy (just docs)

---

### 2.4 RMTA Phase 2+ (P2)

Automated MCP testing orchestrator. Phase 1 (shell harness) is complete.

**Remaining:**
- [ ] Phase 2: Automated orchestrator (`llmc test-mcp --mode ruthless`)
- [ ] Phase 3: CI integration with quality gates
- [ ] Phase 4: Historical tracking and regression detection

---

### 2.5 Onboarding Polish (P2)

- [ ] Auto-run validation after `repo add`
- [ ] Integration with `rag doctor`
- [ ] Embedding model availability check

---

## 3. Later (R&D)

### 3.1 RAG Scoring System 3.0 🔥

**Status:** 🟢 SDD Complete - Ready for Implementation  
**Added:** 2025-12-19

**Problem:** Semantic search for implementation queries returns docs before code.

**Solution:** 4-phase architectural evolution to Graph-Enhanced Dynamic Retrieval:

| Phase | Focus | Effort | Expected Gain |
|-------|-------|--------|---------------|
| **1** | RRF Fusion + Code@k Metric | 8-12h | +10-15% code precision |
| **2** | Graph Neighbor Expansion | 12-16h | +15-20% recall |
| **3** | Z-Score Fusion + SetFit Router | 16-24h | +20-30% intent accuracy |
| **4** | LLM Setwise Reranking | 8-12h | +5-10% top-3 precision |

**📄 Full SDD:** `DOCS/planning/SDD_RAG_Scoring_System_3.0.md`

**Research Basis:** 285KB of academic literature synthesized from RepoGraph (ICLR 2025), RANGER, SetFit, Pinecone Hybrid Search studies.

**Total Effort:** 44-64 hours | **Difficulty:** 🟡 Medium (phased)

---

### 3.2 Distributed Parallel Enrichment

**Problem:** Single-host, synchronous enrichment underutilizes multi-GPU homelab.

**Architecture:**
```
         ┌──────────────────────────────────────┐
         │       ENRICHMENT DISPATCHER          │
         │   (async queue, work stealing)       │
         └──────────────┬───────────────────────┘
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
 [Athena:11434]   [Desktop:11434]   [Laptop:11434]
  (3 concurrent)   (1 concurrent)    (1 concurrent)
```

**Phases:**
| Phase | Description | Effort |
|-------|-------------|--------|
| 0 | Async refactor (httpx) | 8-12h |
| 1 | Multi-host dispatcher | 12-16h |
| 2 | Per-host concurrency | 8-12h |
| 3 | Result aggregation | 8-12h |
| 4 | Per-host metrics | 4-8h |

**Total Effort:** 40-60 hours | **Difficulty:** 🔴 Hard

---

### 3.3 Chat Session RAG

**Idea:** Use LLMC's chunking/embedding pipeline for past conversations.
- Semantic search: "That conversation where we discussed X"
- Inject context from past sessions into bx agent

**Why Later:** Core code RAG still has priority. Nice to have.

---

### 3.4 Configurable Tool Calling Format

**Context:** LLMC uses OpenAI format (industry standard), but Anthropic's XML format is cleaner.

**Goal:** Make format configurable per-profile:
```toml
[profiles.boxxie]
tool_format = "openai"  # Default

[profiles.claude-agent]
tool_format = "anthropic"  # XML-based
```

**Effort:** 8-12 hours | **Difficulty:** 🟢 Easy

---

## 4. How to Use This Roadmap

- Start a work session → pick ONE item from **Now**
- When something is truly done → move to `ROADMAP_COMPLETED.md`
- Periodically reshape **Next** and **Later** based on what's exciting

The goal is a **small, accurate map** of where LLMC is going from here.

