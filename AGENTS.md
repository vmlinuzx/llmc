## AGENTS.md — LLMC Agent Charter

User: **Dave**

- **Repo root:** `~/src/llmc`
- NO RANDOM CRAP IN REPO ROOT. Scratch scripts go in `./.trash/`.

---

## 1. Basic Rules

- Run **smoke tests** after code changes.
- Follow **GitHub best practices**: feature branches, small commits.
- **Never** run destructive git commands (`reset`, `revert`, `rm`) without explicit approval.
- When Dave says "run tests", run them immediately.

---

## 2. RLM Tools (Primary Interface)

**RLM (Recursive Language Model)** is the core capability. Use it for **deep analysis**, not simple searches.

### 2.1 When to Use RLM

| Task Type | Use RLM |
|-----------|---------|
| "Trace the data flow from A to B" | ✅ |
| "Why is X broken?" | ✅ |
| "Refactor X to pattern Y" | ✅ |
| Architectural audit | ✅ |

**Rule:** If the task requires understanding **logic flow**, **debugging**, or **multi-file reasoning**, use RLM.

### 2.2 How to Use RLM

Run via shell command:

```bash
# Analyze a specific file
llmc-cli rlm query "Explain how this works" --file llmc/rlm/budget.py

# Analyze a concept (navigates codebase automatically)
llmc-cli rlm query "How does MCP authentication work?"

# Override budget (default $1.00)
llmc-cli rlm query "Find race conditions" --file session.py --budget 2.0

# Show reasoning trace
llmc-cli rlm query "Find the bug" --file buggy.py --trace
```

**Arguments:**
- First positional: The task/question (required)
- `--file`: File path to analyze (optional, navigates codebase if omitted)
- `--budget`: Cost limit in USD (default 1.0)
- `--trace`: Show reasoning steps

### 2.3 RLM Error Codes

| Code | Meaning |
|------|---------|
| `tool_disabled` | RLM feature flag off |
| `path_denied` | Policy blocks path |
| `file_too_large` | Exceeds size limit |
| `timeout` | Query took too long |

---

## 3. Testing

```bash
pytest tests/                    # All tests
pytest tests/rlm/                # RLM tests
ruff check .                     # Lint
mypy llmc/                       # Type check
```

---

## 4. After Reading This

Read **CONTRACTS.md** for environment details if needed.
