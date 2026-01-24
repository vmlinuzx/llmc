# Upgrade Demon Analysis Report - 2026-01-16

**Type:** Automated Script (not LLM agent)
**Analysis Focus:** Upgrade paths, migration safety, and backwards compatibility.

This report analyzes the codebase with a focus on identifying potential issues for users upgrading from a previous version. The analysis centers on database schema changes, configuration migration, and significant architectural shifts.

## Summary of Findings

| Severity | Finding                               | Component(s) Affected                             | Recommendation                                                                      |
|----------|---------------------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------|
| **P0**   | No Automated DB Schema Migration      | `llmc/rag/database.py`, RAG SQLite databases        | Implement a schema migration framework (e.g., using `PRAGMA user_version`).         |
| **P1**   | Major Backend Architectural Change    | `llmc_agent/backends/*`, `llmc.toml`, `llmc_agent/config.py` | Document the breaking change to LiteLLM and provide clear migration instructions. |
| **P1**   | Breaking Configuration Changes        | `llmc.toml`, `llmc/rag/config_models.py`            | Document new `[mcp.workspaces]` and model configuration precedence.                 |
| **P2**   | Lack of explicit DB rollback safety   | `llmc/rag/database.py`                              | Document manual rollback steps and risks.                                           |

---

## P0: No Automated DB Schema Migration

**Severity:** Critical

**Observation:**
The application uses SQLite for its RAG index (`index_v2.db`) and graph database (`rag_graph.db`). The analysis of `llmc/rag/database.py` and `llmc/rag/work_queue.py` reveals that while the schema is defined with `CREATE TABLE IF NOT EXISTS`, schema alterations are handled via ad-hoc `ALTER TABLE` statements and a helper function `_add_column_if_not_exists`. There is no systematic, versioned migration framework (like Alembic).

The presence of a `schema_version` table is noted, but it is not consistently used to trigger and manage migrations across all database schemas used by the application. The existence of a manual migration script (`scripts/migrate_add_enrichment_metrics.py`) confirms that the process is not fully automated.

**Impact:**
If a developer introduces a schema change without adding the corresponding ad-hoc `ALTER TABLE` logic, existing user databases will become incompatible, leading to runtime errors. This forces users to manually delete their databases and re-index their repositories, resulting in the loss of all existing enrichment data and significant downtime. This is a major barrier to safe and seamless upgrades.

**Recommendation:**
Implement a lightweight but robust database migration mechanism for all SQLite databases. This can be achieved by:
1.  Using `PRAGMA user_version` to store and check the current schema version for each database.
2.  On application startup, compare the database's `user_version` with the application's expected version.
3.  If the database version is lower, apply a series of scripted, incremental `ALTER TABLE` statements to bring the schema up to date. This logic should be centralized.

---

## P1: Major Backend Architectural Change to LiteLLM

**Severity:** High

**Observation:**
The application has migrated from separate, dedicated backends for different LLM providers (`OllamaBackend`, `OpenAICompatBackend`) to a unified `LiteLLM` backend. This is a significant architectural change.
- `DEPRECATED` notices are present in `llmc_agent/backends/ollama.py` and `llmc_agent/backends/openai_compat.py`.
- The `[litellm]` section in `llmc.toml` and `llmc_agent/config.py` is now enabled by default.
- The model configuration format has changed from a simple model name to `provider/model` (e.g., `ollama_chat/qwen3-next-80b-tools`).

**Impact:**
This is a significant breaking change for users with existing `llmc.toml` files.
1.  **Configuration Incompatibility:** Users' existing `[agent]`, `[ollama]`, and `[openai]` sections will be ignored by default. The application will use the default `litellm` configuration, which may not be what the user intends.
2.  **Undocumented Change:** Without clear release notes, users will face unexpected errors or find that their models are not being used as configured.

**Recommendation:**
1.  **Clearly Document the Breaking Change:** The release notes for v0.10.0 must prominently feature this change.
2.  **Provide Migration Guide:** Offer a clear, step-by-step guide on how to migrate an existing `llmc.toml` to the new `litellm` configuration structure.
3.  **(Optional) Add a Compatibility Layer:** Consider adding logic that detects the old configuration structure, prints a loud deprecation warning, and attempts to map it to the new `litellm` settings to provide a smoother transition.

---

## P1: Breaking Configuration Changes

**Severity:** High

**Observation:**
In addition to the `litellm` migration, two other significant configuration changes have been introduced:
1.  **`[mcp.workspaces]`:** The new REST API introduces a `[mcp.workspaces]` table in `llmc.toml` to explicitly define named repository paths. The REST API relies on this section to function.
2.  **Centralized Model Config:** Hardcoded model names have been removed in favor of a centralized `get_default_enrichment_model()` function. This function uses a new precedence: `ENRICH_MODEL` environment variable > `llmc.toml` > first enabled chain's model > a hardcoded fallback.

**Impact:**
1.  **REST API Configuration:** Users wishing to use the new REST API will have to manually add the `[mcp.workspaces]` section to their `llmc.toml`. Old configurations will not work with the API out-of-the-box.
2.  **Model Behavior:** Users who were relying on the old, hardcoded model defaults will find that the application now uses a different model, potentially leading to unexpected changes in behavior or cost.

**Recommendation:**
1.  Documentation for the REST API must clearly explain the requirement for the `[mcp.workspaces]` section.
2.  Release notes must detail the new model configuration precedence to avoid user confusion.

---

## P2: Lack of Explicit DB Rollback Safety

**Severity:** Medium

**Observation:**
The current ad-hoc migration system (`_add_column_if_not_exists` and `ALTER TABLE` statements) only handles forward migrations (upgrades). There is no logic to handle downgrades.

**Impact:**
If a user upgrades to a new version that performs a schema migration and then needs to roll back to a previous version, the older version of the code will likely fail when it encounters the newer, unknown database schema. The only recourse for the user would be to restore their database from a backup or delete it and re-index.

**Recommendation:**
While implementing a full-fledged downgrade migration system is complex, the risk should be documented. The upgrade guide should explicitly state that database migrations are one-way and recommend that users back up their RAG databases (`.rag/` directory) before upgrading.
