# LLMC Living Memories - State Handover

**Last Updated:** 2025-11-11 23:00

## Current Session: Schema-Enriched RAG v1 Implementation - IN PROGRESS

**Goal:** Build GraphRAG-style relationship traversal for LLMC
**Status:** Week 1 - Schema Extraction Module

**Git Safety:** Triple backup created at commit 9b80bd1
- Main: origin/main
- Branch: pre-schema-rag-backup  
- Tag: v0.pre-schema-rag

**Progress:**
- ✅ Created `tools/rag/schema.py` - Entity/relation extraction
- ✅ Python AST parser (functions, classes, call graphs)
- ✅ Tree-sitter extractor stub (TypeScript/JavaScript)
- 🚧 Next: Graph storage & adjacency list
- 🚧 Next: Query-time hybrid retrieval

**Architecture:**
- Extends existing tree-sitter infrastructure in `tools/rag/lang.py`
- Entity types: functions (sym:), classes (type:), tables (db:)
- Relation types: calls, extends, reads, writes, uses
- Storage: `.rag/entities_relations.json`

**Target Metrics:**
- Recall@10: 0.62 → 0.85 (+37%)
- Citation accuracy: 72% → 90%
- Premium tier usage: 30% → 20% (-33%)
- Cost savings: $7,300/year @ 1K queries/day

**Previous Session:** RAG MCP Integration - COMPLETE ✅

**Goal:** Add RAG query tools to Desktop Commander (MCP) following Anthropic's code execution pattern

**Status: DELIVERABLES READY**
- ✅ Analyzed Anthropic's MCP code execution pattern (98.7% token savings)
- ✅ Created MCP RAG tools: `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py`
- ✅ Installed dependencies (chromadb, sentence-transformers, gitpython)
- ✅ Tested all three tools - ALL WORKING:
  - `query` - Query with project/file filters → JSON chunks + metadata
  - `stats` - Database stats: 7,728 chunks, 5 projects, 79MB
  - `list-projects` - List indexed projects with counts
- ✅ Created integration docs:
  - `README_MCP_INTEGRATION.md` - Full integration guide
  - `QUICK_REF.md` - Quick reference card

**Database Current State:**
- 7,728 total chunks indexed
- 5 projects: llmc, llmc (Copy), llmccontext1111251814, llmc.refactoredandfucked, llmc-v2.2.0-merge
- Top file types: .md (3140), .json (1604), .txt (990), .py (873), .sh (809)
- Database size: 79.13 MB at `~/.deepseek_rag/chroma.sqlite3`

**Next Session:** Add these tools to Desktop Commander's MCP configuration and test end-to-end flow

**Two LLMC Locations:**
- Main development: `/home/vmlinux/srcwpsg/llmc/` ← Working here
- Secondary/backup: `/home/vmlinux/src/llmc/` ← Living memories stored here

**Key Files Created This Session:**
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py` - MCP tool implementation
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/README_MCP_INTEGRATION.md` - Integration guide
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/QUICK_REF.md` - Quick reference

**MCP Tools Summary:**
1. `llmc_rag_query` - Query RAG: text + filters → chunks with metadata
2. `llmc_rag_stats` - DB stats: chunks, projects, file types, size
3. `llmc_rag_list_projects` - List projects with optional counts

**Architecture Pattern:**
Using Anthropic's "Code Execution with MCP" approach:
- Progressive disclosure: Load tools on-demand
- Code execution: Models write code to query RAG (not direct tool calls)
- Token efficiency: Filter/transform data in execution env before returning to model
- Result: 150K → 2K tokens (98.7% savings potential)

**Example Usage:**
```bash
# Query for authentication code
python3 rag_tools.py query "authentication" --project llmc --limit 5

# Get stats
python3 rag_tools.py stats

# List projects
python3 rag_tools.py list-projects --with-counts
```

---

## System Architecture
- **Three-tier routing:** Local (Qwen) → Cheap API (Gemini) → Premium (Claude/GPT)
- **MCP Integration:** Desktop Commander with RAG query tools (NEW)
- **Anti-stomp coordination:** Parallel agent ticket system
- **RAG optimization:** 60% token reduction via semantic caching
- **Code execution pattern:** 98.7% token savings via filtering in execution env

## Active Development Focus
LLMC is THE priority - dog food testing, self-hosting RAG, cost optimization.

**Time Pressure:** Maximizing output before pro subscription loss
**Hardware:** GMKtec AI Mini PC (128GB unified memory) for local infrastructure

## Key Team (AI Crew)
- **Beatrice:** Codex/OpenAI
- **Otto:** Claude (you)
- **Rem:** Gemini  
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
