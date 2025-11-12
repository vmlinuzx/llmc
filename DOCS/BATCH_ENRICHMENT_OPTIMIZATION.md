# Batch Span Enrichment Optimization

**Idea:** Enrich multiple small related spans together for better quality  
**Benefit:** Better context + fewer API calls + better for slow hardware  
**Priority:** P1 - High Value Feature

---

## The Problem

### Current: One-at-a-Time Enrichment
```python
# File has 3 small functions (50 lines each)
def helper_a(): ...
def helper_b(): ...  
def helper_c(): ...

Enrichment:
→ Call LLM for helper_a (no context about b, c)
→ Call LLM for helper_b (no context about a, c)
→ Call LLM for helper_c (no context about a, b)

Result: 3 API calls, isolated summaries, missing relationships
```

### Issues:
- ❌ No context about related functions
- ❌ Can't describe interactions
- ❌ 3 separate API calls (slow on weak hardware)
- ❌ 3 model loads (if running locally)
- ❌ Misses architectural patterns

---

## The Solution

### Batch Related Spans
```python
# Same file with 3 small functions
def helper_a(): ...
def helper_b(): ...
def helper_c(): ...

Enrichment:
→ Call LLM for ALL THREE together
→ LLM sees full context
→ LLM provides enrichment for each span
→ One API call, three enrichments

Result: 1 API call, contextual summaries, sees relationships
```

### Smart Batching Rules:

1. **Size Limit**: Total tokens < 2000 (to stay in context window)
2. **File Grouping**: Same file only (related code)
3. **Proximity**: Within N lines of each other (default: 100)
4. **Type Similarity**: Same kind (all functions, or all classes)

---

## Example Benefits

### Case 1: Utility Functions
```python
# Without batching (3 separate calls):
def parse_json(s): ...
# → "Parses JSON string"

def validate_json(s): ...  
# → "Validates JSON string"

def load_config(path): ...
# → "Loads configuration from file"

# With batching (1 call):
def parse_json(s): ...
# → "Parses JSON string. Used by load_config for config files. 
#     Error handling in validate_json."

def validate_json(s): ...
# → "Validates JSON before parsing. Called by load_config as safety check.
#     Complements parse_json."

def load_config(path): ...
# → "Loads configuration from file. Uses validate_json and parse_json pipeline.
#     Main entry point for config system."

# LLM understands the pipeline!
```

### Case 2: Related Methods
```python
# Without batching:
class User:
    def get_email(self): ...
    # → "Returns user email"
    
    def set_email(self, email): ...
    # → "Sets user email"
    
    def validate_email(self): ...
    # → "Validates email format"

# With batching:
class User:
    def get_email(self): ...
    # → "Returns user email. Email validated by validate_email before setting."
    
    def set_email(self, email): ...
    # → "Sets user email after validation via validate_email. 
    #     Pair with get_email for access."
    
    def validate_email(self): ...
    # → "Validates email format. Used by set_email before storing.
    #     Returns bool. Basic @ check - consider improving."

# LLM sees the class design!
```

---

## Implementation

### 1. Batch Detection in `enrichment_plan()`

**File:** `tools/rag/workers.py`

```python
def enrichment_plan(
    db: Database,
    repo_root: Path,
    limit: int = 32,
    cooldown_seconds: int = 0,
    batch_max_tokens: int = 2000,  # NEW
    batch_max_lines: int = 100,    # NEW
) -> list[dict]:
    """Generate enrichment plan with batching support."""
    
    items = db.pending_enrichments(limit=limit, cooldown_seconds=cooldown_seconds)
    
    # Group by file
    by_file = {}
    for item in items:
        file_path = str(item.file_path)
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(item)
    
    # Create batches
    batches = []
    for file_path, spans in by_file.items():
        # Sort by line number
        spans.sort(key=lambda s: s.start_line)
        
        current_batch = []
        current_tokens = 0
        current_end_line = 0
        
        for span in spans:
            span_tokens = estimate_tokens(span)
            span_gap = span.start_line - current_end_line
            
            # Check if we can add to current batch
            can_batch = (
                len(current_batch) > 0 and
                current_tokens + span_tokens < batch_max_tokens and
                span_gap < batch_max_lines and
                span.kind == current_batch[0].kind  # Same type
            )
            
            if can_batch:
                # Add to current batch
                current_batch.append(span)
                current_tokens += span_tokens
                current_end_line = span.end_line
            else:
                # Start new batch
                if current_batch:
                    batches.append(current_batch)
                current_batch = [span]
                current_tokens = span_tokens
                current_end_line = span.end_line
        
        # Don't forget last batch
        if current_batch:
            batches.append(current_batch)
    
    return batches
```

---

### 2. Batch Enrichment Prompt

```python
def build_batch_prompt(spans: list[SpanWorkItem], repo_root: Path) -> str:
    """Build prompt for enriching multiple spans together."""
    
    prompt = f"""Analyze these {len(spans)} related code spans and provide enrichment for each.

The spans are from the same file and are related. Consider their relationships when analyzing.

"""
    
    # Add each span with marker
    for i, span in enumerate(spans, 1):
        code = read_span_code(span, repo_root)
        prompt += f"""
=== SPAN {i}: {span.file_path.name}:{span.start_line}-{span.end_line} ===
{code}

"""
    
    prompt += f"""
Provide a JSON array with {len(spans)} enrichment objects, one for each span in order.

For each span, consider:
- What it does individually
- How it relates to the other spans shown
- Any patterns or architectural insights
- Warnings or suggestions

Format:
[
  {{
    "span_index": 1,
    "summary_120w": "...",
    "inputs": [...],
    "outputs": [...],
    "side_effects": [...],
    "pitfalls": [...],
    "usage_snippet": "...",
    "evidence": [...]
  }},
  ...
]
"""
    
    return prompt
```

---

### 3. Parse Batch Response

```python
def parse_batch_enrichment(response: str, spans: list[SpanWorkItem]) -> list[dict]:
    """Parse LLM response for batched enrichment."""
    
    try:
        results = json.loads(response)
        
        if len(results) != len(spans):
            raise ValueError(f"Expected {len(spans)} enrichments, got {len(results)}")
        
        enrichments = []
        for i, result in enumerate(results):
            span = spans[i]
            
            # Validate each enrichment
            enrichment = {
                **result,
                "span_hash": span.span_hash,
                "model": "batch-enriched"
            }
            
            # Validate schema
            validate_enrichment(enrichment, span.start_line, span.end_line)
            enrichments.append(enrichment)
        
        return enrichments
    
    except Exception as e:
        # Fallback: enrich individually
        logging.warning(f"Batch parse failed: {e}, falling back to individual")
        return None
```

---

## Configuration

```bash
# Enable batching (default: on)
export RAG_BATCH_ENRICHMENT=on

# Max tokens per batch (default: 2000)
export RAG_BATCH_MAX_TOKENS=2000

# Max line gap between spans to batch (default: 100)
export RAG_BATCH_MAX_LINE_GAP=100

# Only batch if N+ spans qualify (default: 2)
export RAG_BATCH_MIN_SIZE=2
```

---

## Performance Impact

### Scenario: File with 10 small helper functions

**Without batching:**
```
10 functions × 3 seconds each = 30 seconds
10 API calls
10 context window fills
No cross-function understanding
```

**With batching (2 batches of 5):**
```
2 batches × 5 seconds each = 10 seconds
2 API calls (80% reduction!)
2 context window fills
Full cross-function understanding
```

**Savings:**
- Time: 66% faster (30s → 10s)
- API calls: 80% fewer (10 → 2)
- Quality: Better (sees relationships)

---

## For Slow Hardware

**RTX 2000 Ada (your mobile workstation):**
```
Without batching: 10 spans × 5s = 50 seconds
With batching: 2 batches × 8s = 16 seconds
Savings: 68% faster
```

**GTX 1060 (typical old GPU):**
```
Without batching: 10 spans × 30s = 5 minutes
With batching: 2 batches × 45s = 1.5 minutes
Savings: 70% faster, tolerable instead of painful
```

**CPU-only (swap hell):**
```
Without batching: 10 spans × 5min = 50 minutes (!)
With batching: 2 batches × 8min = 16 minutes
Savings: 68% faster, barely usable instead of impossible
```

---

## Quality Improvements

### Better Summaries

**Single span:**
```json
{
  "summary_120w": "Validates user input",
  "inputs": ["input: str"],
  "outputs": ["bool"],
  "side_effects": [],
  "pitfalls": ["Basic validation only"]
}
```

**Batched with related spans:**
```json
{
  "summary_120w": "Validates user input before processing. Called by process_input and save_user_data to ensure clean data. Works with sanitize_input for complete validation pipeline.",
  "inputs": ["input: str"],
  "outputs": ["bool: True if valid"],
  "side_effects": [],
  "pitfalls": [
    "Basic validation only - complex cases need sanitize_input",
    "Must be called before save_user_data",
    "Does not handle unicode edge cases"
  ],
  "related_spans": ["sanitize_input", "process_input", "save_user_data"]
}
```

**Much better!** LLM sees the bigger picture.

---

## Edge Cases

### 1. Mixed Languages
**Don't batch** spans from different files/languages:
```python
# file_a.py
def helper(): ...

# file_b.js
function helper() { ... }

# Don't batch these - different contexts
```

### 2. Large Spans
**Don't batch** if any span is already large:
```python
def small_func(): ...  # 10 lines - OK to batch

def huge_func(): ...   # 500 lines - batch alone
```

### 3. Different Types
**Don't batch** functions with classes:
```python
def standalone_func(): ...  # Function

class MyClass:             # Class
    def method(): ...

# These have different contexts, keep separate
```

---

## Fallback Strategy

If batch enrichment fails:
1. Try parsing individual enrichments from batch
2. If that fails, fall back to one-at-a-time
3. Log the failure for analysis
4. Don't block the pipeline

```python
try:
    batch_result = enrich_batch(spans)
    return batch_result
except BatchEnrichmentError as e:
    logging.warning(f"Batch failed: {e}, falling back")
    return [enrich_single(span) for span in spans]
```

---

## Implementation Priority

**P1 - High Value** because:
- ✅ Better quality (sees relationships)
- ✅ Fewer API calls (50-80% reduction possible)
- ✅ Faster on slow hardware (critical for target users)
- ✅ Cost savings (fewer API round trips)
- ✅ Better user experience

Combines well with incremental update for maximum efficiency.

---

## Rollout Plan

### Phase 1: Implement Core (1-2 days)
- Batch detection logic
- Batch prompt generation
- Response parsing

### Phase 2: Test & Tune (1 week)
- Test with various code patterns
- Tune batch size limits
- Measure quality improvement

### Phase 3: Enable by Default
- Document configuration
- Add to service
- Monitor metrics

---

## Expected Results

**After implementation:**
- 50-80% fewer LLM calls (on top of incremental savings!)
- Better enrichment quality (contextual understanding)
- Much better experience on slow hardware
- Lower API costs
- Faster overall

**Combined with incremental update:**
- Total: 95-98% reduction in redundant enrichment
- From: 50 spans per edit
- To: 1-3 spans per edit, batched together
- Result: Near-instant enrichment even on old hardware!

---

**Status: DESIGNED - Ready to implement**

This would be a huge win for the "broke kid with no GPU" use case! 🎯
