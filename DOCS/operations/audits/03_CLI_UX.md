# Audit Charter: CLI & User Experience

**Target Systems:**
*   `llmc/cli.py` (Main entry point)
*   `llmc/tui/` (Rich/Textual interfaces)
*   `llmc/mcgrep.py` (Search output formatting)

**The Objective:**
The CLI must feel "native." It should snap. It should not flicker. It should not dump stack traces on the user.

**Specific Hunting Grounds:**

1.  **The Import Tax (Startup Latency):**
    *   Run `time python3 -m llmc.cli --help`.
    *   If it takes > 200ms, audit the top-level imports.
    *   Are we importing `pandas` or `pytorch` at the module level? (Lazy import everything!)

2.  **The Flicker Fest:**
    *   `llmc/tui/`.
    *   Are we clearing the screen and redrawing unnecessarily?
    *   Does the `Rich` console auto-detect width correctly, or does it guess and wrap uglily?

3.  **The Formatting Bottleneck:**
    *   `llmc/mcgrep.py`.
    *   When showing 100 search results, do we construct 100 `Syntax` objects before printing the first one?
    *   Output should be streamed.

4.  **The Error Vomit:**
    *   Trigger an error (e.g., search for a non-existent repo).
    *   Do we get a nice "Repo not found" message, or a 50-line Python Traceback?
    *   Tracebacks are for developers (logs). Messages are for users (stderr).

**Command for Jules:**
`audit_cli --persona=architect --target=llmc/cli`
