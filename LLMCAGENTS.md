# LLMC Agent Instructions

> **Add this to your AGENTS.md / CLAUDE.md:**  
> `Read and follow ~/.llmc/LLMCAGENTS.md OR <repo>/.llmc/LLMCAGENTS.md for code analysis.`

## What is LLMC?

LLMC provides **RLM (Recursive Language Model)** - a code analysis tool that achieves **80-90% context reduction** compared to reading raw files.

Instead of stuffing your context window with 500 lines of code, RLM:
1. Loads code into a sandboxed Python environment
2. Uses recursive sub-calls to navigate and analyze
3. Returns only the **answer** - not the code

---

## 🚀 The One Tool You Need

```
rlm_query(task, path=None, context=None, ...)
```

### Usage Patterns

**Analyze a file:**
```python
rlm_query(
    task="How does authentication work in this file?",
    path="src/auth/handler.py"
)
```

**Analyze code in context:**
```python
rlm_query(
    task="What does this function do? Are there any bugs?",
    context="""
def process_payment(user_id, amount):
    if amount > get_balance(user_id):
        return False
    deduct(user_id, amount)
    return True
"""
)
```

**Multi-hop trace:**
```python
rlm_query(
    task="Trace the data flow from user input to database write",
    path="src/api/routes.py",
    max_turns=10
)
```

---

## Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | str | **required** | The question or analysis task (max 5000 chars) |
| `path` | str | None | File path to analyze (mutually exclusive with context) |
| `context` | str | None | Raw text to analyze (mutually exclusive with path) |
| `budget_usd` | float | 1.00 | Max cost for this query |
| `max_turns` | int | 5 | Max reasoning iterations |
| `max_bytes` | int | 262144 | Max file bytes to read |
| `timeout_s` | int | 300 | Hard timeout (seconds) |
| `language` | str | None | Language hint (python, javascript, etc.) |

---

## Why RLM vs. Reading Files?

| Approach | Tokens Used | Accuracy |
|----------|-------------|----------|
| Read 500-line file | ~15,000 | Variable (lost-in-the-middle) |
| **RLM query** | ~2,000 | High (focused analysis) |

**RLM saves 80-90% of context tokens** by:
- Lazy loading only relevant code sections
- Recursive decomposition of complex questions  
- Returning summaries, not raw code

---

## When to Use RLM

| Use Case | RLM? | Why |
|----------|------|-----|
| "How does X work?" | ✅ Yes | Perfect for understanding code flow |
| "Find bugs in this file" | ✅ Yes | Focused analysis, clear answer |
| "Trace data flow" | ✅ Yes | Multi-hop navigation built-in |
| Quick syntax check | ❌ No | Just read the file |
| Simple grep/find | ❌ No | Use grep/glob tools |
| Edit a known file | ❌ No | Just edit directly |

---

## Example Session

**User:** "How does the payment flow work?"

**Agent:**
```python
result = rlm_query(
    task="Explain the payment flow from API request to database commit. List the key functions involved.",
    path="src/payments/processor.py",
    max_turns=8
)
# Returns: { "data": { "answer": "The payment flow works as follows:..." } }
```

Instead of reading a 600-line file, you get a focused answer using ~2k tokens.

---

## Error Handling

RLM returns structured errors:

```python
{
    "error": "File too large: 500,000 bytes (max 262,144)",
    "meta": {
        "error_code": "file_too_large",
        "retryable": False,
        "remediation": "Increase max_bytes or use 'context' with truncated text"
    }
}
```

Common error codes:
- `file_too_large` - Use `max_bytes` or pass truncated context
- `timeout` - Increase `timeout_s` or simplify the task
- `path_denied` - File outside allowed roots
- `invalid_args` - Check task length, path/context exclusivity

---

## CLI Quick Reference

```bash
# Check if repo is indexed (for semantic search fallback)
llmc-cli repo list

# Register a new codebase
llmc-cli repo register /path/to/project

# Semantic search (uses pre-computed enrichments)
llmc-cli analytics search "payment processing"
```

---

## Key Insight

**Don't read code files into your context window.** 

Use `rlm_query` to ask questions about code. The answer comes back - the code stays external. This is the "context externalization" paradigm.

---

*Version: 2025-01-26 - RLM Paradigm*
