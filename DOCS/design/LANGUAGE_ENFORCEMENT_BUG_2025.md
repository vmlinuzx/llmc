# Language Enforcement Bug - Critical Finding

**Date:** 2025-11-22  
**Status:** CONFIRMED BUG  
**Severity:** HIGH

---

## The Problem

### Prompt Requirements (in `scripts/qwen_enrich_batch.py`)
```python
prompt = f"""Return ONLY ONE VALID JSON OBJECT in ENGLISH.
...
- summary_120w: <=120 English words describing what the code does.
...
JSON RESPONSE LATIN-1 CHARACTERS ONLY:"""
```

### Actual Output
- **23 enrichment records** contain **Chinese characters** (中文)
- Models used: `qwen2.5:7b-instruct-q4_K_M`, `qwen2.5:14b-instruct-q4_K_M`
- Examples:
  - "路由查询到相应的处理层级、模型和决策理由。"
  - "存儲豐富化數據，插入或替換記錄。"
  - "定义嵌入后端类，包含初始化及几个未实现的方法。"

---

## Root Cause

**The prompt is being IGNORED by the qwen2.5 model.**

The prompt explicitly requests:
1. ❌ English language output
2. ❌ Latin-1 characters only

But the model responds in Chinese anyway because:
- `qwen2.5` is a Chinese-trained model that defaults to Chinese
- Single-pass prompts are not strong enough to override model behavior
- No post-processing validates language compliance

---

## Impact

- ❌ Data pollution with non-English content
- ❌ Violation of explicit user requirements (Latin-1 only)
- ❌ Poor user experience (Chinese in English-only system)
- ❌ Potential compliance issues if Latin-1 is a hard requirement

---

## Solution Options

### Option 1: Strengthen Prompt (Recommended for v1)
Add multiple, forceful language constraints:

```python
prompt = f"""CRITICAL: Respond ONLY in English. NO Chinese characters allowed.
Return ONLY ONE VALID JSON OBJECT in ENGLISH.
...
- summary_120w: <=120 English words ONLY describing what the code does.
...
MUST RESPOND IN ENGLISH ONLY. Use Latin-1 characters ONLY.
Chinese characters are FORBIDDEN. Non-English output will be rejected.
...
JSON RESPONSE MUST BE IN ENGLISH (ASCII/Latin-1):"""
```

**Pros:** Quick fix, no architecture changes  
**Cons:** May still be ignored by model

### Option 2: Use Different Model
Switch to English-only models:
- `llama2:7b` (English)
- `mistral:7b` (English)
- `codellama:7b` (English)

**Pros:** Model will naturally output English  
**Cons:** May have different quality for code understanding

### Option 3: Post-Processing Filter
Add language validation before storing:

```python
def validate_language(output: dict) -> dict:
    if contains_non_latin1(output['summary']):
        # Retry with stricter prompt or mark as failed
        raise LanguageError("Non-Latin-1 characters detected")
    return output
```

**Pros:** Guarantees compliance  
**Cons:** May lose data, requires retry logic

### Option 4: Multi-Stage Prompting
1. First prompt: "Respond in English only"
2. Second prompt: Validate and ask for translation if needed
3. Final prompt: Format as JSON

**Pros:** Higher success rate  
**Cons:** More API calls, slower

---

## Immediate Action Required

**For Dave's Go-Live:** Fix this BEFORE pushing enrichment data to production.

**Recommended Fix (Option 1):**
1. Update `build_prompt()` in `qwen_enrich_batch.py`
2. Add 5-7 forceful English-only instructions
3. Add "Chinese characters forbidden" explicitly
4. Test with known Chinese-enclined code
5. Reprocess all Chinese enrichments

**Time Estimate:** 1-2 hours for fix + testing

---

## Validation

After fix, verify:
- [ ] All new enrichments are English-only
- [ ] No Chinese characters in any field
- [ ] ASCII/Latin-1 compliance verified
- [ ] Existing Chinese records reprocessed

---

## Files to Modify

1. **`scripts/qwen_enrich_batch.py`** - Line ~671 (build_prompt function)
2. **Database** - Reprocess Chinese records after fix

