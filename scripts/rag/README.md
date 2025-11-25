# DeepSeek RAG System - Complete Setup Guide

## What This Is

**Full RAG (Retrieval Augmented Generation) system for DeepSeek Coder**

Your entire `~/src/` workspace is indexed with vector embeddings. When you ask DeepSeek a question, it automatically retrieves relevant code from ALL your projects as context.

## Architecture

```
Your Task
  ↓
Query RAG System (vector search)
  ↓
Find top 10 relevant code chunks from ~/src/
  ↓
Build context (within 6K token budget)
  ↓
DeepSeek Coder 6.7B + Context
  ↓
Smart, context-aware answer
```

## Installation

### 1. Install Python Dependencies

```bash
cd ~/src/glideclubs/scripts/rag

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

This installs:
- **chromadb** - Vector database (runs locally!)
- **sentence-transformers** - Embeddings (runs locally!)
- **watchdog** - File watcher
- **fastapi** - Web UI
- **gitpython** - Git integration

**All runs locally. No API keys needed for RAG.**

### 2. Index Your Workspace

```bash
# Index everything under ~/src/
python index_workspace.py

# This will:
# - Scan all projects in ~/src/
# - Extract code chunks
# - Generate embeddings (local, free)
# - Store in ChromaDB at ~/.deepseek_rag/

# Expected time: 5-10 minutes for ~50 projects
# Storage: ~100-200MB
```

### 3. Verify It Worked

```bash
# Check stats
python index_workspace.py --stats

# Should show:
#   Total chunks: ~50000+
#   Projects indexed: ~50
#   Project list: glideclubs, aegis1, ...
```

### 4. Test Queries

```bash
# Search for authentication code
python query_context.py "authentication system"

# Search in specific project
python query_context.py "supabase queries" --project glideclubs

# Build full context for a task
python query_context.py "add email validation" --project glideclubs --context
```

## Usage

### Automatic (Integrated with llm_gateway)

```bash
# Just use llm_gateway normally - RAG happens automatically!
cd ~/src/glideclubs
echo "Add email validation to signup form" | ./scripts/llm_gateway.sh --local

# DeepSeek will automatically:
# 1. Query RAG for relevant code
# 2. Build context from your project
# 3. Use context to give smart answers
```

### Manual Query

```bash
# Search your codebase
python query_context.py "api routes" --project glideclubs --limit 5

# Build context for DeepSeek
python query_context.py "refactor auth" --project glideclubs --context > context.txt
```

### Web UI (deprecated / unsupported)

```bash
# NOTE: This old FastAPI web UI is deprecated, not supported,
# and likely no longer works on current LLMC setups.
# It is kept only for historical reference.
# Start web interface (legacy / best-effort only)
python rag_server.py

# Visit: http://localhost:8765
# Legacy UI to search and browse your code (may be broken)
```

### File Watcher (Auto-reindex on changes)

```bash
# Watch entire workspace
python watch_workspace.py

# Watch one project
python watch_workspace.py --project glideclubs

# Leave running in background
# Files auto-reindex when you edit them
```

## What Gets Indexed

### Included:
- All code files: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`
- Config files: `.json`, `.yaml`, `.yml`
- Docs: `.md`, `.txt`
- Stylesheets: `.css`, `.scss`
- SQL: `.sql`
- Scripts: `.sh`, `.bash`

### Excluded:
- `node_modules/`, `.git/`, `dist/`, `build/`
- Binary files, images, videos
- Lock files (`package-lock.json`)
- Files > 1MB

## How Context Building Works

```python
Task: "Add email validation to signup form"
Project: glideclubs

RAG System:
1. Convert task to embedding
2. Query ChromaDB for similar code
3. Find top 10 relevant chunks:
   - app/members/join/page.tsx (0.92 relevance)
   - lib/validation.ts (0.89 relevance)
   - app/api/members/join/route.ts (0.85 relevance)
   ...

4. Build context string:
   ```
   # Project: glideclubs
   # Task: Add email validation
   
   ## Relevant Code:
   
   ### app/members/join/page.tsx
   [shows existing form code]
   
   ### lib/validation.ts
   [shows existing validation patterns]
   ```

5. Send to DeepSeek with context
6. DeepSeek gives context-aware answer!
```

## Cost & Performance

```
Indexing (one-time):
- Time: 5-10 min for 50 projects
- Storage: 100-200MB
- Cost: $0 (all local)

Querying:
- Time: <100ms per query
- Cost: $0 (all local)

Model:
- DeepSeek Coder 6.7B on your RTX 2000 Ada
- Speed: 5-10 tok/sec
- Cost: $0 (all local)

Total API costs: $0
Total subscription costs: $0
```

## Commands Reference

```bash
# Initial index
python index_workspace.py

# Reindex everything
python index_workspace.py --reindex

# Index one project
python index_workspace.py --project glideclubs

# Stats
python index_workspace.py --stats

# Query
python query_context.py "search term"
python query_context.py "search term" --project glideclubs
python query_context.py "search term" --context

# Web UI (deprecated / unsupported)
python rag_server.py   # legacy, may be broken
# Visit http://localhost:8765 (legacy UI)

# File watcher
python watch_workspace.py
python watch_workspace.py --project glideclubs

# Integrated with llm_gateway (automatic)
./scripts/llm_gateway.sh --local "your task"
```

## Advanced: Cross-Project Learning

The killer feature: **DeepSeek learns from ALL your projects**

Example:
```bash
# Working on new project
cd ~/src/new-api-project

# Ask about authentication
echo "How should I implement JWT auth?" | ../glideclubs/scripts/llm_gateway.sh --local

# DeepSeek searches RAG across ALL projects:
# - Finds your glideclubs auth implementation
# - Finds your aegis1 API patterns
# - Combines knowledge from multiple projects
# - Gives answer based on YOUR established patterns

# Result: Consistent architecture across all your projects!
```

## Troubleshooting

**"RAG context unavailable"**
```bash
# Index not created yet
python index_workspace.py
```

**"No results found"**
```bash
# Check if project is indexed
python index_workspace.py --stats

# Reindex specific project
python index_workspace.py --project glideclubs --reindex
```

**"Model not found: deepseek-coder:6.7b"**
```bash
# Pull the model
ollama pull deepseek-coder:6.7b
```

**Slow queries**
```bash
# Reduce number of results
python query_context.py "search" --limit 5

# Reduce max tokens for context
python query_context.py "search" --context --max-tokens 4000
```

## What's Next

- ✅ Phase 1: Indexer (DONE)
- ✅ Phase 2: Query system (DONE)
- ✅ Phase 3: Web UI + File watcher (DONE)
- ✅ Integration with llm_gateway (DONE)

**Optional enhancements:**
- [ ] Incremental indexing (only changed files)
- [ ] Multiple embedding models
- [ ] Fine-tune relevance scoring
- [ ] Code-specific chunking (by function/class)
- [ ] Git blame integration (who wrote this?)

## Files Created

```
scripts/rag/
├── requirements.txt ............... Python dependencies
├── index_workspace.py ............. Index ~/src/ into ChromaDB
├── query_context.py ............... Query and build context
├── watch_workspace.py ............. Auto-reindex on file changes
└── rag_server.py .................. Deprecated legacy Web UI (FastAPI; not supported)

scripts/
└── llm_gateway.js ................. Updated with RAG integration

~/.deepseek_rag/ ................... ChromaDB storage (auto-created)
```

## The Executive Win

You now have:
- ✅ RAG system across ALL your projects
- ✅ DeepSeek knows your entire codebase
- ✅ Cross-project learning
- ✅ Zero API costs (all local)
- ✅ Auto-updating (file watcher)
- ✅ Beautiful web UI

**This is the foundation for true AI pair programming that knows YOUR code, YOUR patterns, YOUR style.**

---

**Status:** ✅ ALL PHASES COMPLETE
**Cost:** $0/month (everything local)
**Storage:** ~200MB
**Next:** Run `python index_workspace.py` to index your workspace!
