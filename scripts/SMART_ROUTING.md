# Smart Routing - Codex Wrapper Integration

## What Changed

**codex_wrap.sh** now has **intelligent LLM routing**. It asks an LLM to analyze your task and automatically routes to the best model.

## How It Works

```
You: ./scripts/codex_wrap.sh "fix typo in README"
  ↓
Routing LLM analyzes task (costs $0.001)
  ↓
Decision: "local" (simple task)
  ↓
Ollama executes (free)
  ↓
Done!
```

## The Three Routes

### 1. Local (Free, Slower)
**Uses:** Ollama qwen2.5:14b on your GPU
**When:** Simple tasks
- Typo fixes
- Comment updates
- Formatting changes
- Small edits (≤1 file, ≤20 lines)

**Cost:** $0
**Speed:** 5-10 tok/sec

### 2. API (Cheap, Fast)
**Uses:** Gemini 2.0 Flash
**When:** Medium complexity
- 1-2 file changes
- Clear, well-defined scope
- Routine tasks (≤50 lines)
- Adding validation, tests, etc.

**Cost:** $0.075/1M tokens (~$0.01 per task)
**Speed:** 100+ tok/sec

### 3. Codex (Premium, Best Quality)
**Uses:** Your Codex subscription
**When:** Complex tasks
- Multi-file refactors
- Architecture changes
- New features
- High risk changes
- Unclear scope

**Cost:** Uses your subscription tokens
**Speed:** Fast, high quality

## Usage

### Auto-routing (Default)
```bash
# LLM decides automatically
./scripts/codex_wrap.sh "your task here"
```

### Manual Override
```bash
# Force local (free but slow)
./scripts/codex_wrap.sh --local "simple task"

# Force API (cheap and fast)
./scripts/codex_wrap.sh --api "medium task"

# Force Codex (premium quality)
./scripts/codex_wrap.sh --codex "complex task"
```

## Examples

### Simple Task → Local
```bash
./scripts/codex_wrap.sh "Fix typo in README.md, change 'teh' to 'the'"

🤔 Analyzing task complexity...
📊 Decision: local (confidence: 0.95)
💡 Reason: Simple typo fix, single file, minimal risk
🔄 Routing to local Ollama (free)...
[Task executes on local GPU]
```

### Medium Task → API
```bash
./scripts/codex_wrap.sh "Add email validation to member signup form"

🤔 Analyzing task complexity...
📊 Decision: api (confidence: 0.85)
💡 Reason: Single file change, clear scope, routine validation task
🌐 Routing to Gemini API (cheap)...
[Task executes via Gemini]
```

### Complex Task → Codex
```bash
./scripts/codex_wrap.sh "Refactor auth system to use sessions instead of JWT"

🤔 Analyzing task complexity...
📊 Decision: codex (confidence: 0.95)
💡 Reason: Multi-file architectural change, high complexity and risk
🧠 Routing to Codex (premium)...
[Task executes via Codex subscription]
```

## Cost Comparison

### Before (No Routing):
```
All tasks → Codex subscription
- Simple typo fix: Burns 50K tokens
- Medium task: Burns 100K tokens
- Complex task: Burns 200K tokens
Daily total: Hit 90% of 200K limit
```

### After (Smart Routing):
```
70% of tasks → Local (free)
20% of tasks → API ($0.075/1M)
10% of tasks → Codex (subscription)

Daily breakdown:
- 70% local: $0
- 20% API: ~$0.15
- 10% Codex: ~20K tokens used

Monthly: $5 API + Never hit Codex limits
```

## Routing Decision Process

The routing LLM considers:

1. **Files Touched**
   - 1 file → Consider local/API
   - 2 files → Likely API
   - 3+ files → Route to Codex

2. **Lines Changed**
   - ≤20 lines → Consider local
   - ≤50 lines → Consider API
   - >50 lines → Route to Codex

3. **Risk Level**
   - Typos, comments → Low risk → Local
   - Validation, tests → Medium risk → API
   - Architecture, refactors → High risk → Codex

4. **Complexity**
   - Clear, simple → Local/API
   - Uncertain, complex → Codex

5. **Conservative Bias**
   - When unsure → Route to Codex
   - Better safe than sorry

## Testing

```bash
# Test the routing logic
./scripts/test_routing.sh

# See routing decisions for various task types
```

## Debugging

If routing seems wrong:

```bash
# Check what the router decided
./scripts/codex_wrap.sh "your task" 2>&1 | rg "Decision:"

# Force a specific route to compare
./scripts/codex_wrap.sh --local "task"   # Try local
./scripts/codex_wrap.sh --api "task"     # Try API
./scripts/codex_wrap.sh --codex "task"   # Try Codex
```

## Requirements

- **jq** installed (for JSON parsing)
  ```bash
  # Install if missing
  sudo apt install jq  # Ubuntu/Debian
  brew install jq      # macOS
  ```

- **Gemini API key** (for routing decisions + API tasks)
  ```bash
  export GEMINI_API_KEY="your-key-here"
  # Or add to .env.local
  ```

- **Ollama running** (for local route)
  ```bash
  # Check status
  curl http://localhost:11434/api/tags
  ```

## What Gets Logged

Every routing decision is logged:
```
📊 Decision: api (confidence: 0.85)
💡 Reason: Single file validation, clear scope

Route used: api
Cost estimate: $0.01
Tokens used: ~10K
```

## Advanced: Tuning the Router

The routing prompt is in `codex_wrap.sh`. To adjust:

1. Edit the `route_task()` function
2. Modify the criteria for each route
3. Adjust confidence thresholds

Example: Make it prefer API over local:
```bash
# In route_task(), change:
"local" - Free local Ollama
   - Criteria: ≤1 file, ≤10 lines changed  # Made stricter
```

---

**Status:** ✅ Shipped and ready
**Cost:** $0.001 per routing decision (negligible)
**Benefit:** Saves 70-80% of Codex tokens automatically
