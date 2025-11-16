# HOW TO TEST RAG SYSTEM

## Quick Answer:

**NO, localhost:3000 won't test this** (that's your Next.js app)

RAG works in the **command line** with DeepSeek.

## Step-by-Step Testing:

### 1. Setup First (if not done)
```bash
cd ~/src/glideclubs/scripts/rag
./setup_rag.sh
# Wait 5-10 minutes for indexing
```

### 2. Test RAG Database
```bash
cd ~/src/glideclubs/scripts/rag
python index_workspace.py --stats

# Should show:
#   Total chunks: 40000+
#   Projects: 50+
```

### 3. Test RAG Query
```bash
python query_context.py "authentication" --project glideclubs

# Should show relevant files from your project
```

### 4. Test DeepSeek + RAG Integration
```bash
cd ~/src/glideclubs

echo "How do we handle authentication?" | ./scripts/llm_gateway.sh --local

# Watch for:
#   ✅ RAG context loaded
#   🤖 DeepSeek response using YOUR files
```

### 5. Test Web UI (Optional)
```bash
cd ~/src/glideclubs/scripts/rag
python rag_server.py

# Visit: http://localhost:8765
# NOT localhost:3000 (that's your Next.js app!)
```

## The Two Web UIs:

```
localhost:3000 .......... Your GlidingClubs Next.js app
                         (nothing to do with RAG)

localhost:8765 .......... RAG exploration UI
                         (search your code, see embeddings)
```

## Which Models Work with RAG?

```
✅ DeepSeek Coder 6.7B .... YES (via llm_gateway.sh --local)
✅ Any Ollama model ....... YES (qwen, llama, etc.)
❌ Gemini API ............. NO (not integrated)
❌ Codex .................. NO (not integrated)
```

**To add RAG to other models:**
- Gemini: Doesn't need it (1M context window)
- Codex: Could add but uses subscription

## Simple Test Commands:

```bash
# Test 1: Does RAG exist?
ls ~/.deepseek_rag

# Test 2: Can I query it?
cd ~/src/glideclubs/scripts/rag
python query_context.py "test"

# Test 3: Does DeepSeek use it?
cd ~/src/glideclubs  
echo "What is this project?" | ./scripts/llm_gateway.sh --local
# Look for: "✅ RAG context loaded"

# Test 4: Web UI
cd ~/src/glideclubs/scripts/rag
python rag_server.py
# Visit http://localhost:8765
```

## Automated Test:

```bash
cd ~/src/glideclubs
chmod +x scripts/test_rag_integration.sh
./scripts/test_rag_integration.sh

# Runs all tests automatically
```

## What Success Looks Like:

### Before RAG:
```
You: "How do we handle auth?"
DeepSeek: "You can use JWT tokens. Here's a generic example..."
```

### After RAG:
```
You: "How do we handle auth?"

🔄 Trying local Ollama...
✅ RAG context loaded (8 files found)
   - lib/auth.ts
   - middleware.ts
   - app/api/auth/route.ts

DeepSeek: "Based on lib/auth.ts, you use Supabase Auth with 
RLS policies. The middleware.ts checks auth tokens on protected 
routes. For new endpoints, follow the pattern in 
app/api/auth/route.ts where you use getSupabaseClient()..."
```

**See the difference?** DeepSeek cites YOUR actual files!

## Common Confusion:

❌ "Can I ask questions in my Next.js app at localhost:3000?"
→ No, that's your project, not the AI system

❌ "Does RAG work with Codex automatically?"  
→ No, only with local Ollama models (--local flag)

✅ "How do I use RAG?"
→ Just use llm_gateway.sh --local, it works automatically

✅ "Can I see what RAG found?"
→ Yes! Visit http://localhost:8765 (rag_server.py)

## Integration Status:

```
Tool                    RAG Enabled?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
llm_gateway.sh --local  ✅ YES (automatic)
llm_gateway.sh --api    ❌ NO  (uses Gemini)
codex_wrap.sh (local)   ✅ YES (routes to gateway)
codex_wrap.sh (codex)   ❌ NO  (uses subscription)
```

## To Add RAG to Other Models:

Edit `llm_gateway.js` and add similar RAG context building
to the other completion functions (geminiComplete, etc.)

But honestly? DeepSeek local + RAG is the sweet spot.
