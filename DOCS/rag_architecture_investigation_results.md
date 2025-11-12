# RAG Architecture Investigation - Findings & Recommendations

**Date:** 2025-11-12 11:00
**Investigator:** Otto (Claude)
**Status:** Investigation Complete ✅

## Executive Summary

**Current State:** RAG integration is wrapper-owned (codex_wrap.sh, claude_wrap.sh, gemini_wrap.sh)
**Former State:** Gateway-owned (llm_gateway.js), but was removed in "Phase 2"
**Recommendation:** Keep wrapper-owned architecture BUT standardize the implementation

## Investigation Findings

### 1. Gateway Code Analysis (`llm_gateway.js`)

**Line 246 Evidence:**
```javascript
// RAG plan is now handled by the wrapper script, so we just use the prompt as-is.
// prompt = attachRagPlan(prompt, ragQuery); 
```

**Key Findings:**
- RAG code is **commented out** in gateway
- Comment explicitly states "handled by wrapper script"
- Gateway still has `ragQueryEnv` and `ragQuery` variables but doesn't use them
- This was a deliberate architectural decision ("Phase 2")

**Status:** Gateway is RAG-free ✅

### 2. Wrapper Scripts Analysis

All three wrappers (`claude_wrap.sh`, `codex_wrap.sh`, `gemini_wrap.sh`) follow the same pattern:

**Function:** `rag_plan_snippet()`
```bash
rag_plan_snippet() {
  local user_query="$1"
  if [ "${CLAUDE_WRAP_DISABLE_RAG:-0}" = "1" ]; then
    return 0
  fi
  local index_path
  if ! index_path="$(resolve_rag_index_path)"; then
    return 0
  fi
  local script="$ROOT/scripts/rag_plan_snippet.py"
  if [ ! -x "$script" ]; then
    return 0
  fi
  local output
  if ! output=$(LLMC_RAG_INDEX_PATH="$index_path" "$PYTHON_BIN" "$script" --repo "$ROOT" --limit "${RAG_PLAN_LIMIT:-5}" --min-score "${RAG_PLAN_MIN_SCORE:-0.4}" --min-confidence "${RAG_PLAN_MIN_CONFIDENCE:-0.6}" --no-log <<<"$user_query" 2>/dev/null); then
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "claude_wrap: rag plan failed" >&2
    return 0
  fi
  output="$(printf '%s' "$output" | sed '/^[[:space:]]*$/d')"
  if [ -n "$output" ]; then
    printf '%s\n' "$output"
  fi
}
```

**Call Site:** Inside `build_prompt()`
```bash
build_prompt() {
  local prompt=""
  
  # Bootstrap contract first
  prompt="$(bootstrap_contract)\n\n---\n\n"
  
  # Load AGENTS.md
  # ... agent context ...
  
  # Load CONTRACTS.md
  # ... contract context ...
  
  # RAG CALLED HERE
  local rag_context
  rag_context=$(rag_plan_snippet "$1") || rag_context=""
  if [ -n "$rag_context" ]; then
    prompt="$prompt$rag_context\n\n---\n\n"
  fi
  
  # Add directive and user prompt
  prompt="$prompt<otto_directive>...</otto_directive>\n\n---\n\n$1"
  echo "$prompt"
}
```

**Status:** Wrapper-owned RAG is active ✅

### 3. Helper Script Analysis (`rag_plan_snippet.py`)

**Purpose:** Does the actual RAG database query

**Flow:**
1. Wrapper calls `rag_plan_snippet(user_query)`
2. Wrapper calls Python script: `rag_plan_snippet.py`
3. Python script queries RAG index
4. Returns top N relevant code spans
5. Wrapper appends to prompt

**Status:** Working as intended ✅

## Architecture Assessment

### Current Architecture (Wrapper-Owned)

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  Wrapper Script                 │
│  (claude_wrap.sh)               │
│                                 │
│  build_prompt() {               │
│    1. Bootstrap contract        │
│    2. Load AGENTS.md            │
│    3. Load CONTRACTS.md         │
│    4. rag_plan_snippet()  ←──┐  │
│    5. Add user query         │  │
│  }                           │  │
└──────────────┬───────────────│──┘
               │               │
               │      ┌────────┴─────────┐
               │      │ rag_plan_snippet │
               │      │    .py           │
               │      │                  │
               │      │ - Query RAG DB   │
               │      │ - Return spans   │
               │      └──────────────────┘
               │
               v
┌───────────────────────┐
│   LLM Gateway         │
│   (llm_gateway.js)    │
│                       │
│   - Route to model    │
│   - No RAG logic      │
└──────────┬────────────┘
           │
           v
┌──────────────────┐
│   LLM (Claude)   │
└──────────────────┘
```

**Pros:**
- ✅ Single responsibility - gateway is pure routing
- ✅ Wrapper has full control of context assembly
- ✅ Can customize RAG per wrapper (codex vs claude vs gemini)
- ✅ RAG errors don't affect gateway
- ✅ Easy to disable RAG per wrapper

**Cons:**
- ❌ Code duplication across 3 wrappers
- ❌ Each wrapper must maintain identical RAG logic
- ❌ Changes to RAG require updating 3 files

### Alternative Architecture (Gateway-Owned)

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  Wrapper Script                 │
│  (claude_wrap.sh)               │
│                                 │
│  build_prompt() {               │
│    1. Bootstrap contract        │
│    2. Load AGENTS.md            │
│    3. Load CONTRACTS.md         │
│    4. Add user query            │
│  }                              │
└──────────────┬──────────────────┘
               │
               v
┌────────────────────────────────┐
│   LLM Gateway                  │
│   (llm_gateway.js)             │
│                                │
│   attachRagPlan() {            │
│     - Query RAG DB       ←─────┤
│     - Prepend spans to prompt  │
│   }                            │
│   - Route to model             │
└──────────┬─────────────────────┘
           │
           v
┌──────────────────┐
│   LLM (Claude)   │
└──────────────────┘
```

**Pros:**
- ✅ Single RAG implementation
- ✅ No duplication across wrappers
- ✅ Centralized RAG logic
- ✅ Gateway handles all enrichment

**Cons:**
- ❌ Gateway has multiple responsibilities (routing + RAG)
- ❌ Harder to customize RAG per model
- ❌ RAG failures affect gateway stability
- ❌ More complex gateway code

## Why Phase 2 Moved RAG to Wrappers

Based on code comments and architecture, **Phase 2 was a deliberate simplification:**

1. **Single Responsibility Principle:** Gateway should route, not enrich
2. **Flexibility:** Each wrapper can customize RAG behavior
3. **Isolation:** RAG failures don't crash gateway
4. **Visibility:** Wrapper controls full prompt assembly

**Evidence:** Line 246 in `llm_gateway.js` shows this was intentional

## Recommendations

### Primary Recommendation: Keep Wrapper-Owned Architecture ✅

**Rationale:**
- Phase 2 decision was sound
- Current architecture is cleaner
- Gateway is simpler and more stable
- Each wrapper can optimize for its model

**BUT:** Address the code duplication issue

### Solution: Standardize RAG Implementation

**Problem:** Same code in 3 wrappers (claude_wrap.sh, codex_wrap.sh, gemini_wrap.sh)

**Solution:** Extract to shared library

**New Architecture:**
```bash
# scripts/rag_common.sh (NEW FILE)
rag_plan_snippet() {
  # Shared implementation
  # All wrappers source this file
}
```

**Updated Wrappers:**
```bash
# claude_wrap.sh
source "$SCRIPT_ROOT/scripts/rag_common.sh"

build_prompt() {
  # Use shared rag_plan_snippet()
  local rag_context=$(rag_plan_snippet "$1")
  # ...
}
```

**Benefits:**
- ✅ Eliminates duplication
- ✅ Maintains wrapper-owned architecture
- ✅ Single source of truth for RAG logic
- ✅ Easy to update/fix bugs
- ✅ Keeps gateway simple

### Implementation Plan

1. **Create** `scripts/rag_common.sh`:
   - Extract `rag_plan_snippet()` from claude_wrap.sh
   - Extract `resolve_rag_index_path()` function
   - Make it sourceable by all wrappers

2. **Update** claude_wrap.sh, codex_wrap.sh, gemini_wrap.sh:
   - Add `source "$SCRIPT_ROOT/scripts/rag_common.sh"` at top
   - Remove duplicated functions
   - Keep wrapper-specific logic

3. **Test:**
   - Verify all 3 wrappers still work
   - Confirm RAG still functions
   - Check error handling

4. **Clean Up:**
   - Remove commented RAG code from `llm_gateway.js` (optional)
   - Update documentation
   - Mark `investigate_rag_integration.md` as RESOLVED

## Issues to Address

### 1. Silent Failures ❌

**Current Code:**
```bash
if ! output=$(...command... 2>/dev/null); then
  return 0  # Silently fail
fi
```

**Problem:** Errors are completely hidden

**Recommendation:**
```bash
if ! output=$(...command... 2>&1); then
  [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "RAG failed: $output" >&2
  return 0
fi
```

### 2. Environment Variable Inconsistency

**Current:**
- `CLAUDE_WRAP_DISABLE_RAG` - Claude wrapper
- `CODEX_WRAP_DISABLE_RAG` - Codex wrapper (probably)
- Different names per wrapper

**Recommendation:**
- Use unified `LLMC_DISABLE_RAG` across all wrappers
- Or keep wrapper-specific but document clearly

### 3. Configuration Duplication

**Current:**
- `RAG_PLAN_LIMIT=5`
- `RAG_PLAN_MIN_SCORE=0.4`
- `RAG_PLAN_MIN_CONFIDENCE=0.6`
- Duplicated in each wrapper

**Recommendation:**
- Move to shared `rag_common.sh` with defaults
- Allow wrapper overrides if needed

## Action Items

- [ ] Create `scripts/rag_common.sh` with shared RAG functions
- [ ] Update `claude_wrap.sh` to source `rag_common.sh`
- [ ] Update `codex_wrap.sh` to source `rag_common.sh`
- [ ] Update `gemini_wrap.sh` to source `rag_common.sh`
- [ ] Test all wrappers work correctly
- [ ] Improve error handling (remove silent failures)
- [ ] Standardize environment variables
- [ ] Remove commented RAG code from `llm_gateway.js`
- [ ] Update `investigate_rag_integration.md` with RESOLVED status
- [ ] Document the wrapper-owned RAG architecture

## Conclusion

**Decision:** Keep wrapper-owned RAG architecture (Phase 2 decision was correct)

**Fix:** Eliminate duplication by extracting to `rag_common.sh`

**Status:** Investigation complete, ready for implementation

**Next Steps:**
1. Create shared RAG library
2. Update all wrappers to use it
3. Test thoroughly
4. Mark architectural investigation as resolved
