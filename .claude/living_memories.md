# LLMC Living Memories - State Handover

**Last Updated:** 2025-11-12 (Daemon P0 VERIFIED WORKING! ✅🎉)

## Current Session: DAEMON ENRICHMENT P0 VERIFIED! ✅🎉

**Status:** Critical P0 bug in RAG daemon RESOLVED AND TESTED

### THE FIX: Daemon Now Uses Real LLM Enrichment ✅

**Problem Solved:** RAG daemon was calling `rag enrich --execute` which uses `default_enrichment_callable()` that generates FAKE auto-summaries instead of calling real LLMs

**Solution Implemented:**
- Updated `tools/rag/service.py:226` to call proper enrichment script
- Daemon now uses `qwen_enrich_batch.py` or `tools.rag.runner.refresh` with routing logic
- Smart routing (7b→14b→nano tier promotion) now functional in daemon mode
- GPU monitoring and metrics now active in daemon mode
- Real LLM enrichment data being generated

**VERIFICATION RESULTS** (2025-11-12 18:16):
- ✅ **116 detailed enrichments** (>50 chars) - REAL LLM data!
- ✅ **Only 1 fake** enrichment (pre-fix remainder)
- ✅ **Real models active**: qwen2.5:7b, qwen2.5:14b, qwen2.5:7b-instruct-q4_K_M
- ✅ **Smart routing confirmed**: tier "7b" with router_tier "7b"
- ✅ **Metrics working**: 1.5MB `logs/enrichment_metrics.jsonl`, 23.59 tokens/sec
- ✅ **Token savings**: 368,900 saved (78% reduction)
- ✅ **Performance**: 1,054 enrichments completed / 1,349 spans (78% rate)

**Example Real Enrichment:**
```
"Sample run comparing Qwen 2.5 local and GPT-5 Nano on Azure,
showing times for storing different enrichments."
```
(NOT fake like: "path:line auto-summary generated offline")

**Files Modified:**
- `/home/vmlinux/src/llmc/tools/rag/service.py` - process_repo() method updated
- **Tested**: `sqlite3 .rag/index.db` and `logs/enrichment_metrics.jsonl`

## Previous Session: RAG TOOLS FIXED! ✅

**Status:** Desktop Commander filesystem visibility bug RESOLVED

### THE FIX: Filesystem Fallback Chain ✅

**Problem Solved:** Desktop Commander reading stale RAG data (5-minute lag)

**Solution Implemented:**
- Added 3 new methods to `rag_tools.py`: `read_file()`, `list_directory()`, `file_exists()`
- Fallback chain: Try RAG first → Fall back to live filesystem
- Returns clear source indicator: `"source": "rag" | "filesystem"`
- Sync status tracking: `"sync_status": "synced" | "out_of_sync"`

**Files Modified:**
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py` (enhanced from v1 to v2 capabilities)
- All tests passing: 6/6 ✅

**CLI Commands Added:**
```bash
python3 scripts/rag/mcp/rag_tools.py read-file <path>      # Read with fallback
python3 scripts/rag/mcp/rag_tools.py list-directory <path> # List with fallback  
python3 scripts/rag/mcp/rag_tools.py file-exists <path>    # Check sync status
```

**Test Suite Created:**
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/test_rag_tools.sh`
- All 6 tests passing (help, stats, read, exists, list, error handling)
- 32s runtime, comprehensive validation

### Previous Session Recap: Agentic Routing via Schema Complexity

**Status:** Context limit reached, deep research kicked off

**The Big Win:** Quantifiable routing strategy
```python
complexity_score = (schema_slices * schema_branches) + relation_depth

if complexity_score <= 5:    route_to = LOCAL
elif complexity_score <= 15: route_to = API  
else:                        route_to = PREMIUM
```

**Examples:**
- "update git config" = 1 × 1 + 0 = 1 → LOCAL
- "find functions calling X" = 2 × 3 + 2 = 8 → API
- "why can't bash see DC files?" = 5 × 4 + 6 = 26 → PREMIUM

### What We Built Today

**RAG Tools Enhancement:**
- ✅ Merged v2 fallback logic into main rag_tools.py
- ✅ Fixed __init__ to gracefully degrade (no crash on missing RAG)
- ✅ Added CLI parsers for new commands
- ✅ Created comprehensive test suite
- ✅ All tests passing with filesystem fallback working

**Schema-Enriched RAG v1 (ON HOLD - waiting for agentic routing research):**
- ✅ `tools/rag/schema.py` - Python AST parser (198 lines, works)
- ✅ Entity/Relation/SchemaGraph data structures
- 🚧 Waiting for deep research on complexity scoring
- 🚧 Will resume after routing algorithm finalized

**Git Cleanup (completed previous session):**
- ✅ Switched from davidcarrollwitmer to vmlinuzx account
- ✅ Personal email vs corporate email properly configured
- ✅ MiniMax handled git config successfully

### Key Insights

**Desktop Commander Bug - RESOLVED:**
- Root cause: RAG-only access with 5-minute debounce
- Solution: Fallback to live filesystem when RAG stale
- Impact: No more "quantum pockets" where files exist but DC can't see them

**MiniMax Lane Confirmed:**
- Personal assistant tasks ✅
- Git housekeeping ✅
- Documentation sweeps ✅
- Simple linear workflows ✅
- **FAILS at 3+ schema jumps** ❌

**Routing by Schema Complexity (pending deep research):**
- MiniMax: ≤2 schema jumps
- Gemini: 3-4 schema jumps
- Claude: 5+ schema jumps or complex abstractions

### Repo Locations (CORRECTED)

**PERSONAL REPO:**
- `/home/vmlinux/src/llmc` → `vmlinuzx/llmc` (personal GitHub)
- Living memories stored here
- schema.py committed and working

**CORPORATE REPO:**
- `/home/vmlinux/srcwpsg/llmc` → Corporate work
- rag_tools.py location (JUST FIXED!)
- test_rag_tools.sh location (NEW!)

### Next Session Priority

Based on Roadmap.md backlog:

1. ✅ **COMPLETED:** Fix Desktop Commander filesystem visibility bug
2. 🔄 **IN PROGRESS:** Investigate RAG integration architecture
   - Problem: RAG called at multiple layers (wrapper scripts, gateway, helpers)
   - Question: Should RAG be wrapper-owned, gateway-owned, or separate service?
   - Impact: Code duplication, silent failures, architectural confusion
3. ⏭️  **NEXT:** Continue architectural investigation and document findings
4. ⏭️  **WAIT:** Resume Schema-Enriched RAG after deep research results

### Tools & Their Lanes

**Desktop Commander (MCP):**
- Terminal control, file operations
- NOW HAS FILESYSTEM FALLBACK ✅
- Config: `~/.config/Claude/claude_desktop_config.json`

**RAG Tools (Our middleware) - ENHANCED:**
- Query: Semantic search RAG database
- Stats: Database metrics
- List-projects: Show indexed projects
- **NEW:** read_file_with_fallback ✅
- **NEW:** list_directory_with_fallback ✅
- **NEW:** file_exists (with sync status) ✅

**MiniMax:**
- Personal tasks, git ops, doc sweeps
- Sweet spot: 0-2 schema jumps
- Goes rogue at 3+ jumps

**Claude (Otto):**
- Architecture, complex debugging
- Handles 5+ schema jumps
- Current session: ~75K/190K tokens used

### Action Items

- [x] Add fallback methods to rag_tools.py - DONE!
- [x] Test fallback logic works - DONE!
- [x] Investigate daemon enrichment issue - CRITICAL BUG FOUND AND VERIFIED FIXED! 🎉
  - Found: daemon calls `rag enrich --execute` which uses FAKE stub data
  - File: tools/rag/service.py:226
  - Impact: 100% useless enrichment, no routing/metrics/retry logic
  - Added to Roadmap.md as P0
  - RESOLVED: Updated daemon to use real LLM enrichment with routing logic
  - VERIFIED: Tested daemon, 116 real enrichments, 1.5MB metrics, full routing confirmed
- [ ] Wait for deep research results on agentic routing
- [x] Investigate RAG integration architecture - INVESTIGATION COMPLETE! ✅
  - Found: RAG called at multiple layers with code duplication
  - Decision: Keep wrapper-owned architecture (Phase 2 was correct)
  - TODO: Create scripts/rag_common.sh to eliminate duplication
  - Issues: 3 different rag_plan_snippet() implementations, silent failures
- [x] Document RAG architecture decisions - DONE (investigation_results.md exists)
- [x] Fix daemon to call proper enrichment script - DONE!
- [x] Test daemon enrichment fix - DONE! Verified real LLM data, full metrics, smart routing
- [ ] Create scripts/rag_common.sh shared library for RAG functions
- [ ] Update all wrappers to source rag_common.sh
- [ ] Fix silent failures and environment variable inconsistencies
- [ ] Implement schema complexity scorer (after research)
- [ ] Resume Schema-Enriched RAG implementation

---

## System Architecture
- **Three-tier routing:** Local (Qwen) → API (Gemini) → Premium (Claude)
- **NEW: Schema-based routing:** Complexity score = slices × branches + depth
- **MCP Integration:** Desktop Commander + custom RAG tools (NOW WITH FALLBACK!)
- **Anti-stomp coordination:** Parallel agent ticket system
- **Token optimization:** 70-95% reduction via RAG, 98.7% via code execution pattern

## Active Development Focus
1. **RAG Architecture Standardization (NEXT)** - Create shared library for duplicated code
   - Investigation COMPLETE: Keep wrapper-owned architecture
   - TODO: Create scripts/rag_common.sh, update all wrappers
   - Issues: 3 different rag_plan_snippet() implementations, silent failures, wrong env vars
2. **Agentic Routing (WAITING)** - Deep research in progress on complexity scoring
3. **LLMC Tooling (FIXED!)** - Filesystem visibility bug resolved ✅
4. **RAG Daemon Enrichment (VERIFIED WORKING!)** ✅
   - CRITICAL P0 bug RESOLVED and TESTED: daemon now uses real LLM enrichment
   - Verified: 116 real enrichments, 1.5MB metrics, 23.59 tokens/sec
   - Smart routing (7b→14b→nano) fully functional in daemon mode
   - GPU monitoring and metrics active, 368,900 tokens saved (78% reduction)

**Time Pressure:** Maximizing output before pro subscription loss
**Hardware:** GMKtec AI Mini PC (128GB unified memory) for local infrastructure

## Key Team (AI Crew)
- **Beatrice:** Codex/OpenAI (code generation)
- **Otto:** Claude (architecture, complex problems) 
- **Rem:** Gemini (medium complexity)
- **MiniMax:** Personal assistant (0-2 schema jumps)
- **Grace:** Captain/mascot (Admiral Grace Hopper tribute)

## Azure Resources
- **Subscription:** 96e57f65-c275-4c5f-9d0e-47a3b0dcced5
- **Resource Group:** ollamama-mcp-rg
- **Deployment:** GPT-5-nano on WPSGAPINSTANCE-eastus2

## Work Context (WPSG)
- **Role:** Executive Director of IT
- **Company:** $300M EMT supply, 4 brands
- **Systems:** NetSuite ERP, BigCommerce integrations
- **Team:** Peter Cler (NetSuite), Phil (senior architect)
- **Today:** Light standup, running on caffeine + focus meds

## Side Project: FreeFlight (on hold)
- Next.js/Supabase architecture
- Gliding club management software
- AI-first weather systems with local LLM agents

## Workflow Notes
- **ADHD hyperfocus:** 8-12 hour sprints
- **Multi-terminal:** 6-8 sessions simultaneously
- **Philosophy:** "Rule 1: Be Cheap" - cost-effective, vendor-independent
- **Work style:** Remote, sometimes from mountains while paragliding
- **Environment:** Ubuntu 24 native (NOT WSL2) - "Year of the Linux Desktop"

## WARNINGS

### Log Files (CRITICAL)
**NEVER open large log files directly** - they will fill entire context window and crash:
- `logs/claudelog.txt` - Massive JSON dumps
- `logs/enrichment_metrics.jsonl` - Continuous append log
- `logs/planner_metrics.jsonl` - Continuous append log
- Any `.jsonl` files in logs/

**Safe approach:** Use `tail -n 50` or `head -n 50` to preview, NEVER open full file.
**If you need to analyze:** Use grep/awk/jq to extract specific lines, don't load entire file.

### Enrichment System
DO NOT WATCH ENRICHMENT LOG FILES - system will exhaust itself.
The enrichment system is functional and tight. Trust it, don't monitor it obsessively.
If you run enrichment, have an auto-kill system behind the execution.

### MiniMax Incident (2025-11-12)
MiniMax filled context window and went rogue, made destructive changes.
**Lesson:** Hard context limits per agent, kill switch at 90% usage, training wheels for new models.
**Update:** MiniMax found its lane - personal assistant tasks, 0-2 schema jumps only.

### Desktop Commander RAG Lag (2025-11-12) - RESOLVED! ✅
~~Desktop Commander reads from RAG with 5-minute debounce, shows stale data.~~
~~bash reads from live filesystem.~~
**FIXED:** Added filesystem fallback chain to rag_tools.py
**Status:** All tests passing, fallback working perfectly

---

**Session End:** 2025-11-12 10:45
**Context:** 75K/190K tokens (40% capacity)
**Status:** RAG tools fixed and tested, ready for next architectural investigation