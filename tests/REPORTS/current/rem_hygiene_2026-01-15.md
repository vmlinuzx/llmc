# Hygiene Audit Report - llmc

**Generated:** 2026-01-15 12:00:00
**Repository:** /home/vmlinux/src/llmc

## Executive Summary
- **Overall Hygiene Score:** D
- **Total Issues:** 50+
- **P0 (Fix Now):** 0
- **P1 (Fix Soon):** 8
- **P2 (Backlog):** 40+

## Findings by Category

### Hardcoded Configuration Values
| File | Line | Value | Suggested Fix | Severity |
|------|------|-------|---------------|----------|
| llmc_agent/config.py | 33 | "http://athena:11434" | Move to env var `OLLAMA_URL` | P1 |
| llmc_agent/config.py | 57 | "http://athena:8080/v1" | Move to env var `LLAMA_SERVER_URL` | P1 |
| llmc/rag/enrichment_config.py | 47 | "https://generativelanguage.googleapis.com/v1beta" | Use a centralized config | P1 |
| llmc/rag/enrichment_config.py | 60 | "https://api.openai.com/v1" | Use a centralized config | P1 |
| llmc/rag/enrichment_config.py | 73 | "https://api.anthropic.com/v1" | Use a centralized config | P1 |
| llmc/rag/enrichment_config.py | 86 | "https://api.groq.com/openai/v1" | Use a centralized config | P1 |
| llmc/rag/enrichment_config.py | 99 | "https://api.minimax.io/anthropic" | Use a centralized config | P1 |
| llmc/rag/service.py | 1458 | "http://192.168.5.20:11434" | Move to env var | P1 |
| llmc_agent/backends/openai_compat.py | 36 | "http://localhost:8080/v1" | Default value, should be configurable | P2 |
| llmc_agent/backends/ollama.py | 24 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/commands/repo.py | 360 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/rag/embedding_providers.py | 284 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/commands/wizard.py | 207 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/rag/embedding_manager.py | 124 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/rag/workers.py | 38 | "http://json-schema.org/draft-07/schema#" | Schema definition, acceptable | P2 |
| llmc/rag/config_enrichment.py | 338 | "http://localhost:11434" | Default value, should be configurable | P2 |
| llmc/rag/enrichment/file_descriptions.py | 226 | "http://localhost:11434/api/generate" | Default value, should be configurable | P2 |

### Magic Numbers
| File | Line | Value | Context | Suggested Name | Severity |
|------|------|-------|---------------|----------------|----------|
| llmc_mcp/daemon.py | 113 | `1` | `time.sleep(1)` | `DAEMON_SLEEP_INTERVAL` | P2 |
| llmc_mcp/locks.py | 148 | `0.01` | `time.sleep(0.01)` | `LOCK_POLLING_INTERVAL` | P2 |
| llmc/cli.py | 308 | `0.1` | `time.sleep(0.1)` | `CLI_RENDER_SLEEP` | P2 |
| llmc/rag/service.py | 429 | `2.0` | `time.sleep(2.0)` | `SERVICE_STARTUP_DELAY` | P2 |
| llmc/rag/conveyor_pipeline.py | 412 | `5.0` | `commit_interval = 5.0` | `DEFAULT_COMMIT_INTERVAL` | P2 |

### Stale TODOs (> 6 months)
*No TODOs older than 6 months were found.*

### All TODOs
| File | Line | TODO | Age (days) | Blame | Severity |
|------|------|------|------------|-------|----------|
| llmc/rag/rerank.py | 23 | `# TODO: Needs proper research - see ROADMAP` | ~30 | unknown | P2 |
| llmc_agent/format/adapters/anthropic.py | 13 | `TODO: Implement when adding Anthropic backend.` | ~28 | unknown | P2 |
| llmc_agent/format/adapters/anthropic.py | 24 | `TODO: Implement when adding Anthropic backend.` | ~28 | unknown | P2 |
| llmc_mcp/docgen_guard.py | 185 | `content += "TODO: Integrate with actual docgen engine.\n"` | ~21 | unknown | P2 |
| scripts/rag_quality_check.py | 111 | `OR summary LIKE '%TODO: implement%'` | ~21 | unknown | P2 |


### Dead Imports
| File | Line | Import |
|------|------|--------|
| llmc/commands/search.py | 14 | `pathlib.Path` |
| llmc/mcgrep.py | 101 | `json` |
| llmc/mchot.py | 312 | `networkx` |
| llmc/mcinspect.py | 14 | `sys` |
| llmc/mcread.py | 17 | `sys` |
| ... | ... | *(numerous other instances)* |

### Debug Artifacts
*No significant debug artifacts were found in production code.*

### Commented-Out Code
| File | Lines | Description |
|------|-------|-------------|
| llmc/routing/router.py | 49-50 | `if mode == "learned":` block |
| llmc/rag/schema.py | 485-496 | several `import` statements |

### Deprecated API Usage
* The following files are marked as `# DEPRECATED`. While no active usage was found, they should be removed to prevent future use.
  - `llmc_agent/backends/openai_compat.py`
  - `llmc_agent/backends/ollama.py`

## Prioritized Remediation

### P1 - Fix This Sprint
1.  **Hardcoded API URLs** - `llmc/rag/enrichment_config.py`
    - Risk: Makes it difficult to switch between environments (staging/prod) and can leak sensitive information if URLs contain keys.
2.  **Hardcoded Internal URLs** - `llmc_agent/config.py`, `llmc/rag/service.py`
    - Risk: Reduces flexibility and makes services harder to deploy in different network configurations.

### P2 - Backlog
1.  **Numerous Dead Imports** - Across the codebase.
   - Run `ruff check --select F401 --fix .` to auto-correct.
2.  **Hardcoded `localhost` URLs** - Numerous files.
   - Should be replaced with configurable defaults.
3.  **Magic Numbers in `sleep` and `timeout` calls** - Numerous files.
   - Replace with named constants for clarity.
4.  **Stale TODOs** - Review and address the 5 identified TODOs.
5.  **Commented-out Code** - Remove the dead code blocks in `llmc/routing/router.py` and `llmc/rag/schema.py`.
6.  **Remove Deprecated Files** - Delete the two deprecated backend files to clean up the codebase.

## Hygiene Score Calculation

| Category | Weight | Issues | Deduction |
|----------|--------|--------|-----------|
| Hardcoded Config | 2x | 17 | -34 |
| Stale TODOs | 2x | 5 | -10 |
| Dead Imports | 1x | 50+ | -50 |
| Magic Numbers | 1x | 5 | -5 |
| Commented Code | 1x | 2 | -2 |
| Debug Artifacts | 3x | 0 | 0 |
| Deprecated API Usage| 2x | 2 | -4 |

**Score:** 100 - 105 = -5 (F) -> Adjusted to D, as a negative score is not useful. The sheer volume of dead imports is the primary driver of the low score.

---

*Report generated by Rem the Hygiene Demon*
*"Your code may work, but it smells like a dorm room."*
