---
name: llmc-orientation
description: Context-optimized codebase orientation for local LLMs. Use skeleton-first exploration to reduce token usage by 85%. Essential when working with limited context windows (<128k tokens) or slow prompt processing.
triggers:
  - llmc
  - codebase
  - explore
  - orientation
  - skeleton
  - context budget
  - token limit
---

# LLMC Orientation Skill

**Purpose**: Guide local LLMs to work efficiently with the LLMC codebase by minimizing context usage.

> **Your context window is precious.** Every token spent on irrelevant code is a token stolen from reasoning.

---

## Core Principle: Skeleton First, Implementation Later

Local models are **bandwidth-bound**. A 70B+ model can take minutes to process 50k+ tokens. To stay interactive:

1. **Orient with skeletons** (signatures only) → ~15% of original tokens
2. **Read implementations only when needed** → surgical precision
3. **Never** open entire files when you only need one function

---

## Workflow

### Step 1: Get the Skeleton

Before exploring ANY code, get the skeleton view:

```bash
# Get skeleton of entire repo (capped to budget)
llmc-cli rag skeleton --repo ~/src/llmc --max-tokens 4000

# Get skeleton of specific directory
llmc-cli rag skeleton --repo ~/src/llmc --paths llmc/rlm

# Get skeleton of single file
llmc-cli rag skeleton-file ~/src/llmc/llmc/rlm/session.py
```

**Output**: Function signatures, class definitions, docstrings only. No implementations.

### Step 2: Target Your Read

Once you know WHAT exists, read ONLY what you need:

```bash
# Read a specific function (not the whole file)
# Use view_code_item or equivalent surgical tool
```

### Step 3: Use RLM for Deep Analysis

For multi-file reasoning, let RLM handle the context management:

```bash
llmc-cli rlm query "How does session.py handle token tracking?" --budget 1.0
```

RLM internally uses skeleton + surgical extraction. Trust it.

---

## Anti-Patterns (DON'T DO THIS)

| ❌ Bad | ✅ Good |
|--------|---------|
| `cat llmc/rlm/session.py` | `llmc-cli rag skeleton-file llmc/rlm/session.py` |
| Read 5 files "for context" | Get skeleton, read 1 targeted function |
| Load entire module | Load specific class/function |
| 30k tokens of imports | Signatures only (~3k tokens) |

---

## Token Budget Guidelines

| Context Size | Strategy |
|--------------|----------|
| < 8k | Skeleton only, no file reads |
| 8k-32k | Skeleton + 1-2 surgical reads |
| 32k-64k | Skeleton + targeted RLM query |
| 64k-128k | Can be more generous, but still prefer surgical |

---

## Key Files to Know

| Path | Purpose | Read When... |
|------|---------|--------------|
| `llmc/main.py` | CLI entrypoint | Understanding commands |
| `llmc/rlm/session.py` | RLM session state | Debugging RLM |
| `llmc/rlm/prompts.py` | System prompts | Modifying behavior |
| `llmc/rlm/config.py` | Configuration | Setup issues |
| `llmc/rag/skeleton.py` | Skeleton generator | Context optimization |

---

## Quick Reference

```bash
# Orientation (always start here)
llmc-cli rag skeleton --repo . --max-tokens 4000

# Deep analysis (let RLM manage context)
llmc-cli rlm query "Explain X" --file path/to/file.py

# Run tests after changes
pytest tests/ -q
```

---

## Why This Matters

| Approach | Tokens | TTFT (Time to First Token) |
|----------|--------|----------------------------|
| Read all relevant files | ~50k | 2-3 minutes |
| Skeleton + surgical | ~8k | 15-30 seconds |

**85% token savings = 5x faster response times** on local inference.
