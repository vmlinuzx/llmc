# Audit Charter: Configuration Hygiene

**Target Systems:**
*   Entire Codebase (`llmc/`, `scripts/`)
*   `llmc.toml` (The Source of Truth)

**The Objective:**
Banishing "Magic Numbers" and "Hardcoded Paths". The system behavior should be controlled by configuration, not by editing python files.

**Specific Hunting Grounds:**

1.  **The Magic Number Hunt:**
    *   Grep for numbers like `32`, `0.5`, `100`, `50`.
    *   *Context:* Why is the batch size `32`? Why is the timeout `0.5`s?
    *   **Verdict:** If it affects performance or behavior, it belongs in `llmc.toml` (e.g., `[rag] batch_size = 32`).

2.  **The Path to Nowhere:**
    *   Grep for string literals containing `/`.
    *   Look for hardcoded paths like `"/tmp"`, `"/home/user"`, or relative paths `"../data"`.
    *   **Verdict:** All paths must be relative to the Project Root (derived dynamically) or configured via env vars/config.

3.  **The "Hidden Env" Trap:**
    *   Grep for `os.getenv` and `os.environ`.
    *   Are these variables documented in `llmc.toml` or `README.md`?
    *   Is there a central `config.py` that loads them? Or are they scattered across 50 files?
    *   **Verdict:** Centralize config loading. Fail fast if required variables are missing.

4.  **The "Default Value" Lie:**
    *   `def connect(timeout=30):`
    *   Is that `30` defined in a constant? Or is it a magic number repeated in 5 function signatures?
    *   **Verdict:** Define defaults in a central `constants.py` or the default config dict.

**Command for Jules:**
`audit_config --persona=architect --target=.`
