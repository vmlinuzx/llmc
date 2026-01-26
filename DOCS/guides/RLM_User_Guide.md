# RLM User Guide

**Recursive Language Model (RLM)** is an agentic analysis engine built into LLMC. Unlike standard RAG (which retrieves snippets based on semantic similarity), RLM acts as a researcher that can navigate your codebase, read files, follow imports, and "think" through complex problems over multiple turns.

---

## 🏗️ What is RLM?

RLM is a **stateful analysis loop**. When you ask RLM a question, it doesn't just guess the answer. It:

1.  **Plans** a research strategy.
2.  **Executes** tools (read file, list directory, grep).
3.  **Analyzes** the results.
4.  **Iterates** until it has a confident answer or runs out of budget.

### When to use RLM vs. RAG

| Feature | Standard RAG (`llmc search`) | RLM (`llmc rlm query`) |
| :--- | :--- | :--- |
| **Best for** | "Where is X?" "How do I usage Y?" | "Why is X broken?" "Refactor Y." "Explain the data flow of Z." |
| **Mechanism** | Vector Similarity + Graph Traversal | Agentic Reasoning Loop (ReAct-style) |
| **Cost** | Very Low (1 turn) | Higher (Multiple turns, many tokens) |
| **Depth** | Surface-level / snippet-based | Deep / analytical |
| **Time** | Seconds | Minutes |

---

## ⚙️ Configuration

RLM is configured in your `llmc.toml` file under the `[rlm]` section.

```toml
[rlm]
enabled = true
# Use a strong model for the root reasoning loop (Planner)
root_model = "ollama_chat/qwen2.5-coder:32b"
# Use a faster/cheaper model for sub-tasks (optional)
sub_model = "ollama_chat/qwen2.5-coder:7b"

[rlm.budget]
# Hard caps to prevent infinite loops or excessive costs
max_session_budget_usd = 1.00  # Stop if estimated cost exceeds $1
max_session_tokens = 500_000   # Stop if total tokens exceed 500k
max_subcall_depth = 5          # Max recursion depth

[rlm.sandbox]
# "process" is standard. "restricted" available for untrusted code (future).
backend = "process"
code_timeout_seconds = 30
allowed_modules = ["os", "sys", "json", "re", "ast"]
```

### Budgeting

RLM tracks token usage for every prompt and completion.
- **`max_session_budget_usd`**: The primary safety brake. Defaults to $1.00.
- **`max_turns`**: Defaults to 20 turns per session.

---

## 🖥️ CLI Usage

The primary way to use RLM is via the CLI:

```bash
# Analyze a specific file
llmc rlm query "Explain how the budget tracker works and if there are race conditions" --file llmc/rlm/budget.py

# Analyze a general concept (starts at repo root)
llmc rlm query "How does the MCP server handle authentication?"

# Adjust budget for a complex query
llmc rlm query "Refactor this module to use dependency injection" --file legacy_code.py --budget 2.0
```

---

## 🔧 Troubleshooting

### Common Errors

**`BudgetExceededError`**
> *The session has exceeded the maximum cost budget of $1.00.*

*   **Cause:** The agent got stuck in a loop or the task was too large.
*   **Fix:** Increase budget with `--budget 2.0` or make the prompt more specific.

**`SandboxTimeoutError`**
> *Code execution timed out after 30 seconds.*

*   **Cause:** The agent tried to run a very slow script or infinite loop.
*   **Fix:** RLM usually catches this and retries. If it persists, check your `code_timeout_seconds` config.

### Reading Trace Logs

Use `--verbose` to see the agent's "thought process":

```bash
llmc rlm query "..." --verbose
```

You will see:
1.  **Thought**: The agent's plan ("I need to check imports...")
2.  **Action**: The code it runs (`list_dir("llmc/core")`)
3.  **Observation**: The output it gets back.

---

## 💡 Example Scenarios

### 1. Performance Analysis
**Task:** "Why is the indexer slow?"

```bash
llmc rlm query "Analyze llmc/rag/indexer.py for performance bottlenecks. Look for N+1 queries or excessive file reads."
```
*RLM will likely:*
1. Read `indexer.py`.
2. Notice a loop calling a database function.
3. Read the database function definition.
4. Report that batching is missing.

### 2. Refactoring
**Task:** "Modernize legacy code."

```bash
llmc rlm query "Refactor this class to use Pydantic v2 instead of dataclasses. Output the new code." --file my_model.py
```
*RLM will:*
1. Read the file.
2. Identify dataclass fields.
3. Rewrite the class using `pydantic.BaseModel`.
4. Validate imports.

### 3. Bug Investigation
**Task:** "Fix the path traversal bug."

```bash
llmc rlm query "Check llmc_mcp/tools/fs.py for path traversal vulnerabilities. Verify if '..' is blocked."
```
*RLM will:*
1. Read the validator code.
2. Write a test case (mentally or in sandbox) to see if `../../etc/passwd` passes.
3. Confirm the regex is sufficient or flawed.

