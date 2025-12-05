# High Level Design: Repo Configurator Integration

Status: Draft  
Owner: Core Team  
Date: 2025-12-03  
Version: 0.3

Encoding: latin-1 friendly (ASCII-only content)

---

## 1. Purpose

This document describes the high level design for the Repo Configurator feature, which generates a per-repository `llmc.toml` configuration during `llmc-rag-repo add`.

The design incorporates the following key decisions:

- Integrate with the existing `llmc-rag-repo add` command, not a new service abstraction.
- Use an existing `llmc.toml` template (LLMC's own or a user-provided template) as the source of truth.
- Preserve comments and formatting using a comment-preserving TOML library (for example, tomlkit).
- Avoid destructive changes to enrichment chains and other complex configuration structures.
- Handle existing `llmc.toml` files safely, with clear user-facing choices and backups.
- Behave safely and predictably when LLMC is installed as a package (pip install).

---

## 2. Scope

### 2.1 In Scope

- Generating a per-repo `llmc.toml` when onboarding a repository with `llmc-rag-repo add`.
- Using an existing `llmc.toml` template as a base and applying minimal, well-defined edits:
  - Update `mcp.tools.allowed_roots` to include the target repo root.
  - Update `tool_envelope.workspace.root` to the target repo root.
  - Optionally append to `indexing.exclude_dirs`.
  - Optionally adjust enrichment chain URL and model for the default chain.
- Interactive prompts in the CLI for overriding a small set of configuration values:
  - Embeddings endpoint and model.
  - Enrichment endpoint and model.
  - Additional directories to exclude from indexing.
- Non-interactive mode that uses template defaults without prompting, suitable for CI.
- Safe handling of existing `llmc.toml` files (keep, replace with backup, or abort).

### 2.2 Out of Scope (v1)

- Automatic merging of an existing per-repo `llmc.toml` with a new template.
- A library of named templates and profiles (python-ml, typescript-web, monorepo, etc.).
- A dedicated `llmc-rag-repo validate` or `llmc-rag-repo diff` command (these can be added later).
- Deep structural refactoring of enrichment chains (for example, replacing all chains with a single custom one).
- Any changes to how `.llmc/rag` workspaces are built or how RAG indexing/enrichment logic works.

---

## 3. Current Behavior

### 3.1 Repository Onboarding

Today, the canonical onboarding path is:

- Command: `llmc-rag-repo add PATH`
- Implementation: `tools/rag_repo/cli.py` (`_cmd_add`)
- Responsibilities:
  - Inspect the target repository.
  - Build a workspace plan.
  - Initialize `.llmc/rag` under the repo root.
  - Register the repo in the RAG registry.

The presence of `llmc.toml` at the repo root is already supported by configuration loaders:

- `tools/rag/config.py::load_config(repo_root)` reads `repo_root / llmc.toml` if present.
- `llmc/te/config.py::get_te_config(repo_root)` reads TE-specific configuration from `llmc.toml`.
- `llmc_mcp/config.py::load_config(config_path)` can also load TOML configuration.

However, there is no automated way today to generate a per-repo `llmc.toml`. Users either hand-write one or copy LLMC's root config and edit paths manually.

### 3.2 LLMC Root Configuration

LLMC itself ships with a root-level `llmc.toml` that:

- Configures embeddings profiles, including provider URLs and models.
- Defines enrichment chains and a default chain (for example, "athena").
- Configures the tool envelope (workspace root, respect_gitignore, etc.).
- Provides documented defaults and examples using comments.

This file acts both as executable configuration and as documentation.

---

## 4. Goals and Non-Goals

### 4.1 Goals

1. Make onboarding a new repository trivial:
   - One command should be enough to get a working `llmc.toml` for that repo.
2. Treat LLMC's existing `llmc.toml` (or a user-provided template) as the golden source:
   - Per-repo configs should be copies of the template with minimal, predictable edits.
3. Preserve human readability:
   - Keep comments and formatting from the template in the per-repo copy.
4. Avoid breaking existing enrichment and routing logic:
   - Do not rewrite enrichment chains in destructive ways.
5. Be safe by default:
   - Do not silently overwrite existing `llmc.toml` files.
   - Always create backups when replacing.
6. Behave conservatively in non-interactive / CI mode:
   - `--yes` should never destroy existing configuration. Existing configs are preserved, not replaced.

### 4.2 Non-Goals

1. It is not a goal to support fully automatic merging of arbitrary existing configs with new templates.
2. It is not a goal to build a general TOML refactoring engine.
3. It is not a goal to design a new configuration schema.
4. It is not a goal to validate network connectivity or model availability in v1 (this can be a separate "doctor" command or a later phase).

---

## 5. High Level Architecture

### 5.1 Overview

The Repo Configurator is a small component that plugs into the existing `llmc-rag-repo add` flow.

High-level call flow:

1. User runs `llmc-rag-repo add /path/to/repo` (or via the unified CLI wrapper).
2. `tools/rag_repo/cli._cmd_add`:
   - Performs the existing workspace and registry steps.
   - Invokes `RepoConfigurator.configure(repo_path, template_path=args.template)`.
3. `RepoConfigurator`:
   - Determines the template `llmc.toml` location:
     - If `--template` is provided, use that file.
     - Otherwise, locate LLMC's root `llmc.toml` (when running from the LLMC repo).
   - Loads the template text and parses it with a comment-preserving TOML library.
   - If a `llmc.toml` already exists in the target repo:
     - Interactive mode: prompt the user to keep, replace, or abort.
     - Non-interactive mode: default to "keep existing" and skip generation.
   - Collects user overrides (interactive mode only).
   - Applies a small set of safe edits to the parsed template document.
   - Writes the new `llmc.toml` to the repo root, with a header comment and backups as needed.

### 5.2 Components

1. RepoConfigurator
   - High-level orchestration class.
   - Responsibilities:
     - Template discovery.
     - Existing-config decision logic.
     - Interactive prompting.
     - Calling lower-level functions to transform and write the config.

2. Template Loader
   - Loads the template file as raw text.
   - Parses the text into a comment-preserving TOML document.
   - Provides helper functions to read:
     - Default embeddings URL and model.
     - Enrichment `default_chain` and associated chain entries.

3. Option Collector
   - Builds an in-memory `ConfigOptions` object.
   - In interactive mode:
     - Prompts the user for overrides with default values based on the template.
   - In non-interactive mode:
     - Uses template values without prompting.

4. Config Transformer
   - Applies edits to the parsed TOML document:
     - Path substitutions.
     - Optional embeddings overrides.
     - Optional enrichment overrides for the default chain.
     - Optional indexing excludes.
   - Avoids changing the structural shape of complex sections like `[[enrichment.chain]]`.

5. Config Writer
   - Handles existing file detection and backup.
   - Writes the transformed TOML document back to disk.
   - Prepends a small header comment noting generation time and template path.

---

## 6. Detailed Design

### 6.1 Integration in CLI

File: `tools/rag_repo/cli.py`

- In `_cmd_add(args)`, after the existing workspace initialization:

  - Determine `repo_path` as a `Path`.
  - After workspace and registry steps succeed, call:

    - `from .configurator import RepoConfigurator`
    - `configurator = RepoConfigurator(interactive=not args.yes)`
    - `configurator.configure(repo_path=repo_path, template_path=args.template)`

- CLI flags to add or extend:
  - `--template PATH`:
    - Optional path to a custom template `llmc.toml`.
    - If omitted, default is LLMC's own root `llmc.toml` when running from the LLMC repo.
  - `-y, --yes`:
    - Already used for non-interactive confirmation in the existing flow.
    - For Repo Configurator, `--yes` means:
      - Do not prompt for embeddings or enrichment overrides.
      - If `llmc.toml` exists in the repo, do not overwrite; simply skip config generation.
      - This behavior should be clearly documented for CI users.

### 6.2 Template Discovery

`RepoConfigurator` will choose a template as follows:

1. If `template_path` is provided:
   - Use that exact file.
2. Else:
   - Attempt to locate LLMC's own root `llmc.toml`:
     - Start from `Path(__file__).resolve().parent`.
     - Walk upwards and look for the first `llmc.toml` (repo checkout scenario).
     - Optionally use an environment variable override (for example, `LLMC_ROOT`) if that exists in the codebase.

If no template `llmc.toml` can be found by discovery:

- In v1, the configurator will:
  - Abort with a clear error message explaining that auto-discovery failed and `--template` is required.
  - Exit with non-zero status.
- This is especially relevant when LLMC is installed via pip and there is no `llmc.toml` near the installed package.

Future enhancements may bundle a default template as package data, but that is out of scope for v1.

### 6.3 Template Loading and Parsing

- Read template file as text (UTF-8).
- Parse with a comment-preserving TOML library (for example, tomlkit):

  - `doc = tomlkit.parse(template_text)`

- The resulting `doc` is a mutable document-like object that:

  - Preserves comments and whitespace where possible.
  - Allows dict-style read/write operations.

- Extract relevant defaults for prompting:

  - Embeddings:
    - Document path: `doc["embeddings"]["profiles"]["docs"]`
    - Default URL: `profile["ollama"]["api_base"]` (if present)
    - Default model: `profile.get("model")`
  - Enrichment:
    - Default chain name: `doc["enrichment"].get("default_chain")`
    - Chains: iterate over `doc["enrichment"]["chain"]` list to find entries where `entry["chain"] == default_chain_name`.

### 6.4 Existing `llmc.toml` Handling

Target path: `repo_path / "llmc.toml"`

Interactive mode:

- If the file does not exist:
  - Proceed to generate a new config.
- If the file exists:
  - Prompt the user:

    - `K`eep existing config.
    - `R`eplace with a new one from template (with backup).
    - `A`bort onboarding.

  - Behavior:
    - K: skip config generation entirely, print a message, and continue.
    - R:
      - Compute backup file name, for example:
        - `llmc.toml.bak.YYYYMMDDHHMMSS`
      - Rename the existing file to the backup name.
      - Proceed to generate and write the new config.
    - A:
      - Abort `_cmd_add` with non-zero exit code.

Non-interactive mode (`--yes`):

- If the file does not exist:
  - Generate new config from the template without prompting.
- If the file exists:
  - Do not modify it.
  - Print a message to stderr stating that `llmc.toml` already exists and that generation was skipped.
  - Continue with the rest of the onboarding steps.

This behavior is conservative by design. For CI and unattended workflows, documentation should clearly state:

- Use `--yes` for unattended operation.
- Existing configs are preserved, not replaced, in non-interactive mode.
- To force replacement in a future version, a dedicated `--force-config` flag can be added (out of scope for v1).

No merging or structural diff is attempted in v1.

### 6.5 Option Collection

`ConfigOptions` is an internal data structure for user choices and overrides. For v1 it includes:

- `repo_path: Path`
- `custom_embeddings_url: str | None`
- `custom_embeddings_model: str | None`
- `custom_enrichment_url: str | None`
- `custom_enrichment_model: str | None`
- `additional_excludes: list[str]`

A concrete example definition (in Python) is:

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ConfigOptions:
    repo_path: Path
    custom_embeddings_url: str | None = None
    custom_embeddings_model: str | None = None
    custom_enrichment_url: str | None = None
    custom_enrichment_model: str | None = None
    additional_excludes: list[str] = field(default_factory=list)
```

The `field(default_factory=list)` avoids the mutable default pitfall and makes the behavior predictable.

Interactive mode:

- Prompt for embeddings:
  - Show default URL and model derived from the template.
  - Ask whether to use the defaults.
  - If the user opts out of defaults, prompt for URL and model.

- Prompt for enrichment:
  - Show a description derived from the template:
    - For example: the name of the default chain and its current model and URL.
  - Ask whether to use the defaults.
  - If the user opts out, prompt for a new URL and model.

- Prompt for indexing excludes:
  - Optionally show a simple summary of the repo (for example, root path).
  - Ask the user for a comma-separated list of directories to exclude.
  - Convert to a list of strings and store in `additional_excludes`.

Non-interactive mode:

- No prompts.
- `ConfigOptions` uses only template-driven defaults and `additional_excludes` remains empty.

### 6.6 Config Transformation

Operating on the parsed template document `doc`, the transformer applies the following operations.

#### 6.6.1 Path Substitution

1. `mcp.tools.allowed_roots`:

   - Ensure the section exists.
   - Replace the value with a one-element list containing the repo path:

     - `doc["mcp"]["tools"]["allowed_roots"] = [str(repo_path)]`

   - For v1, we accept that this may overwrite multiple roots from the template.
   - In documentation, note that `allowed_roots` is reset per repo.

2. `tool_envelope.workspace.root`:

   - Ensure the nested tables exist.
   - Set:

     - `doc["tool_envelope"]["workspace"]["root"] = str(repo_path)`

#### 6.6.2 Embeddings Overrides (Optional)

If `ConfigOptions` contains a custom embeddings URL and/or model:

- Locate the embeddings profile used for documents, for example:

  - `profile = doc["embeddings"]["profiles"]["docs"]`

- Update:

  - If URL provided:
    - `profile["ollama"]["api_base"] = custom_embeddings_url`
  - If model provided:
    - `profile["model"] = custom_embeddings_model`

No other profiles are modified in v1.

#### 6.6.3 Enrichment Overrides (Optional)

If `ConfigOptions` contains a custom enrichment URL and/or model:

- Read `default_chain_name = doc["enrichment"]["default_chain"]`.
- Iterate over `doc["enrichment"]["chain"]` list.
- For each chain entry where `entry["chain"] == default_chain_name`:

  - If URL provided:
    - `entry["url"] = custom_enrichment_url`
  - If model provided:
    - `entry["model"] = custom_enrichment_model`

This intentionally updates all entries that belong to the default chain, not just one row. For example, for:

```toml
[[enrichment.chain]]
name = "athena-ministral-14b"
chain = "athena"

[[enrichment.chain]]
name = "athena-8b"
chain = "athena"
```

both entries will be updated, so the entire cascade for the default chain moves to the new URL and/or model as a group.

Notes:

- The structural shape of `[[enrichment.chain]]` is not changed (no entries are removed or added).
- If the default chain is not found, log a warning and leave enrichment unchanged.

#### 6.6.4 Indexing Excludes (Optional)

If `ConfigOptions.additional_excludes` is non-empty:

- Ensure `doc["indexing"]["exclude_dirs"]` exists and is a list.
- Append each new directory pattern if it is not already present.

Example:

- Template has: `exclude_dirs = ["node_modules", ".git"]`
- User adds: `["build", "dist"]`
- Result: `["node_modules", ".git", "build", "dist"]`

### 6.7 Config Writing

When writing the final per-repo `llmc.toml`:

1. Build a header comment:

   - Example:

     - `# Generated by: llmc-rag-repo add`
     - `# Generated on: 2025-12-03T21:14:11Z`
     - `# Template: /absolute/path/to/template/llmc.toml`
     - `#`

2. Serialize the modified document with the TOML library:

   - `body = tomlkit.dumps(doc)`

3. Write the combined string:

   - `output = header + "\n" + body`
   - Write with UTF-8 encoding.

If a backup was required (replace existing config in interactive mode):

- The backup step must occur before any writes.
- The backup name should be unique (timestamp-based) to avoid overwriting older backups.

---

## 7. Error Handling and Edge Cases

1. Template file not found:
   - Abort with an error message that explains that auto-discovery failed and `--template` is required.
   - Exit non-zero.
2. Template parsing failure:
   - Abort with an error message indicating invalid template TOML.
3. Missing expected sections in template:
   - If `mcp.tools` or `tool_envelope.workspace` sections are missing:
     - The configurator can either:
       - Create these sections, or
       - Abort with a clear message and treat the template as incompatible.
   - For v1, creating missing sections with minimal defaults is acceptable.
4. Enrichment default chain not found:
   - Log a warning and skip enrichment override.
   - Do not modify `enrichment.chain`.
5. File permission issues:
   - If the configurator cannot read the template or write `llmc.toml`, abort with an error message describing the permission problem.
6. User cancellation (interactive):
   - If the user chooses Abort when asked about existing `llmc.toml`:
     - Stop `_cmd_add` and return a non-zero exit code.

---

## 8. Security Considerations

- `allowed_roots` and `tool_envelope.workspace.root` define the filesystem scope for tools and TE.
- The configurator must always set these paths to the intended repo root and not to broader paths (for example, the user's home directory) unless explicitly requested in a later phase.
- User-supplied values (for example, extra exclude directories) are only used to narrow indexing, not to expand tool access.

---

## 9. Compatibility and Migration

- The addition of Repo Configurator does not change behavior for existing repos:
  - It only runs during `llmc-rag-repo add`.
- Existing per-repo `llmc.toml` files are respected:
  - In interactive mode, the user can choose to keep them.
  - In non-interactive mode, they are never modified.
- LLMC's root `llmc.toml` continues to be the canonical template and documentation.
- When LLMC is installed via pip and no template can be found automatically, the behavior is explicit and predictable: configuration generation fails with an error explaining that `--template` must be provided.

---

## 10. Future Work

The following enhancements are explicitly deferred to later phases:

1. Template Library
   - Provide multiple named templates (minimal, python-ml, typescript-web, monorepo).
   - Add `--profile` or similar flag to select a template.

2. Validation Command
   - `llmc-rag-repo validate` to:
     - Check endpoint reachability.
     - Verify models.
     - Validate paths.

3. Diff Command
   - `llmc-rag-repo diff` to show differences between a per-repo `llmc.toml` and the current LLMC template.

4. More Sophisticated Merging
   - Smarter handling of existing per-repo configs when templates change.
   - Possibly driven by header comment metadata (template path, generation time).

This HLD defines a minimal, safe, and pragmatic v1 that can be implemented and shipped quickly while leaving room for those enhancements later.
