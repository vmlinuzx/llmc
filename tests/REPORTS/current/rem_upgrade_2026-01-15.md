# Upgrade Demon Analysis Report - 2026-01-15

**Type:** Automated Script (not LLM agent)
**Analysis Focus:** Upgrade paths, migration safety, and backwards compatibility.

This report analyzes the codebase with a focus on identifying potential issues for users upgrading from a previous version. The analysis centers on database schema changes, configuration migration, and significant architectural shifts.

## Summary of Findings

| Severity | Finding                               | Component(s) Affected                             | Recommendation                                                                      |
|----------|---------------------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------|
| **P0**   | No Automated DB Schema Migration      | `llmc/rag/graph_db.py`, RAG SQLite databases        | Implement a schema migration framework (e.g., using `PRAGMA user_version`).         |
| **P1**   | Major Backend Architectural Change    | `llmc_agent/backends/*`, `llmc.toml`, `llmc_agent/config.py` | Document the breaking change to LiteLLM and provide clear migration instructions. |
| **P2**   | Configuration Drift (Model Names)     | `llmc.toml`, Potentially hardcoded in codebase       | Eliminate all hardcoded model names; pull them from a central configuration.        |
| **P2**   | Manual Config Loading Logic         | `llmc_agent/config.py`                              | Refactor to a more automated config loading mechanism to reduce maintenance burden. |

---

## P0: No Automated DB Schema Migration

**Severity:** Critical

**Observation:**
The application uses SQLite for its RAG index (`index_v2.db`) and graph database (`rag_graph.db`). The analysis of `llmc/rag/graph_db.py` reveals that while the schema is defined with `CREATE TABLE IF NOT EXISTS`, there is no logic to handle schema alterations on existing databases (e.g., `ALTER TABLE ... ADD COLUMN ...`).

The presence of a `schema_version` table is noted, but it is not currently used to trigger or manage migrations.

**Impact:**
If a new version of `llmc` introduces a change to a database schema (e.g., adding a new column required for a feature), the application will fail when writing to an older-version database. This will force users to manually delete their databases and re-index their repositories, resulting in the loss of all existing enrichment data and significant downtime. This is a major barrier to safe and seamless upgrades.

**Recommendation:**
Implement a lightweight but robust database migration mechanism. For SQLite, this can be achieved by:
1.  Using `PRAGMA user_version` to store and check the current schema version.
2.  On application startup, compare the database's `user_version` with the application's expected version.
3.  If the database version is lower, apply a series of scripted, incremental `ALTER TABLE` statements to bring the schema up to date.

---

## P1: Major Backend Architectural Change to LiteLLM

**Severity:** High

**Observation:**
The application is migrating from separate, dedicated backends (`OllamaBackend`, `OpenAICompatBackend`) to a unified `LiteLLM` backend. This is evidenced by:
- `DEPRECATED` notices in `llmc_agent/backends/ollama.py` and `llmc_agent/backends/openai_compat.py`.
- The addition of a `[litellm]` section in `llmc.toml` and `llmc_agent/config.py`, which is enabled by default (`litellm.enabled = true`).
- A change in the model configuration format within `llmc.toml` from a simple model name to `provider/model` (e.g., `ollama_chat/qwen3-next-80b-tools`).

**Impact:**
This is a significant breaking change.
1.  **Configuration Incompatibility:** Users with existing `llmc.toml` files will have configurations that are no longer valid for the new backend. Their existing `[agent]`, `[ollama]`, and `[openai]` sections will not work as expected without manual migration to the `[litellm]` format.
2.  **Undocumented Change:** Without clear release notes, users will face unexpected errors or degraded functionality when their old configuration is not interpreted correctly by the new backend system.

**Recommendation:**
1.  **Clearly Document the Breaking Change:** The release notes for this version must prominently feature this change.
2.  **Provide Migration Guide:** Offer a clear, step-by-step guide on how to migrate an existing `llmc.toml` to the new `litellm` configuration structure.
3.  **(Optional) Add a Compatibility Layer:** Consider adding logic that detects the old configuration structure, prints a loud deprecation warning, and attempts to map it to the new `litellm` settings. This would provide a smoother transition for users.

---

## P2: Configuration Drift and Hardcoded Values

**Severity:** Medium

**Observation:**
1.  **Model Names:** Recent commits and changes in `llmc.toml` show a concerted effort to switch from `qwen2.5` to `qwen3` models. A recent commit (`0bad3e8`) fixed hardcoded model defaults, and another (`ce265b3`) created a task to eliminate them. This indicates that model names may still be hardcoded elsewhere in the codebase, creating a disconnect between the `llmc.toml` configuration and the application's runtime behavior.
2.  **Manual Config Loading:** The `_merge_config` function in `llmc_agent/config.py` manually maps keys from the TOML file to the configuration dataclasses. This pattern is brittle and requires manual updates whenever a new configuration option is added to the dataclasses, creating a potential for drift between the code and the configuration file.

**Impact:**
- **Inconsistent Behavior:** If model names are hardcoded, the application may ignore the settings in `llmc.toml`, leading to confusion and making it impossible for users to configure their desired model.
- **Maintenance Overhead:** The manual config loading logic is a maintenance burden and increases the risk of bugs where new configuration options are ignored because the mapping function wasn't updated.

**Recommendation:**
1.  **Aggressively Purge Hardcoded Models:** Perform a full codebase search for any hardcoded model strings (e.g., `"qwen3:4b-instruct"`) and replace them with references to the `Config` object.
2.  **Refactor Config Loading:** Consider a more automated approach to loading configuration, where the TOML structure directly maps to the dataclass structure, reducing the need for the manual `_merge_config` function. Libraries like `pydantic-settings` or custom reflection-based loaders can solve this elegantly.

---
**Report End**
