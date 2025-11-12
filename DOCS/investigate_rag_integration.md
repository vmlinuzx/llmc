# RAG Integration Architecture Investigation

## Problem Statement
The RAG (Retrieval-Augmented Generation) integration is implemented across MULTIPLE layers in the system, creating architectural confusion and code duplication.

## Current Implementation

### Layer 1: Wrapper Scripts
- `scripts/claude_wrap.sh` - Calls `rag_plan_snippet()` in `build_prompt()`
- `scripts/codex_wrap.sh` - Calls `rag_plan_snippet()` in `build_prompt()`
- Both append RAG context to prompts BEFORE sending to gateway

### Layer 2: LLM Gateway
- `scripts/llm_gateway.js` - Has `attachRagPlan()` function (NOW COMMENTED OUT)
- Has `ragPlanSnippet()` function (still active)
- Uses `RAG_USER_PROPT` environment variable
- **Note:** Line 246 shows "// RAG plan is now handled by the wrapper script"

### Layer 3: Helper Script
- `scripts/rag_plan_helper.sh` - Calls `python3 scripts/rag_plan_snippet.py`
- Does the actual RAG database query

## Issues Identified

1. **Code Duplication** - RAG logic scattered across 3+ layers
2. **Silent Failures** - All error output suppressed with `2>/dev/null`
3. **Inconsistent Behavior** - Some layers call RAG, others don't
4. **Commented Code** - `llm_gateway.js` shows "Phase 2" removing RAG
5. **Architectural Confusion** - Unclear who owns RAG responsibility

## The "Should Not Be Necessary" Question

**Why is RAG being called in BOTH wrapper scripts AND the gateway?**

Current flow:
```
User Query → Wrapper Script → RAG Query → Add Context → Gateway → LLM
                                   ↑
                                   └─ Gateway ALSO has RAG functions!
```

**Better Architecture:**
```
User Query → Wrapper Script → Gateway → LLM
                          ↑
                          └─ Gateway owns RAG (single responsibility)
```

## Investigation Tasks

1. Trace when `attachRagPlan()` was commented out and why
2. Determine if wrapper scripts should handle RAG or gateway should
3. Identify which approach reduces complexity
4. Check if Phase 2 removal was completed
5. Decide on single responsibility: Wrapper OR Gateway (not both)

## Recommendations

**Option A: Wrapper-Only RAG**
- Remove RAG code from `llm_gateway.js`
- Keep RAG in wrapper scripts
- Gateway becomes pure routing/proxy

**Option B: Gateway-Only RAG** (Recommended)
- Remove RAG code from wrapper scripts
- Keep RAG in `llm_gateway.js`
- Uncomment `attachRagPlan()` call
- Wrapper becomes pure routing

**Option C: Unified RAG Service**
- Extract RAG logic to separate service
- Both wrapper and gateway call same service
- Reduces coupling

## Next Steps
1. Decide on architecture (A, B, or C)
2. Remove duplicated code paths
3. Ensure RAG is called exactly once per request
4. Add proper error handling (no more silent failures)
