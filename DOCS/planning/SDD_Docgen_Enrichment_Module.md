SHA256: TODO_FILL_ON_FIRST_IMPL

# SDD – Docgen Enrichment Module (LLMC RAG)

- Kind: docs
- Language: Markdown
- Primary responsibility: Define the design and behavior of a deterministic, idempotent, RAG‑aware documentation generator that runs as a controlled enrichment stage for LLMC, configurable via `llmc.toml` and usable across TUI, CLI, MCP, and remote daemon‑managed repos.

## 1. High-level purpose

This SDD describes a **Docgen Enrichment Module** for LLMC:

- Treat documentation generation as a **first-class enrichment stage** (arguably the most detailed enrichment).
- Run it under control of the **RAG daemon / job runner** so it works for:
  - local repos, and
  - remotely registered repos in the daemon registry.
- Ensure behavior is:
  - **deterministic** (for given inputs),
  - **idempotent** (per file content hash), and
  - **configurable** via `llmc.toml` so different environments can plug in:
    - a shell script that calls Gemini,
    - a local LLM,
    - a remote HTTP API,
    - or an MCP-based tool.
- Leverage the existing LLMC **RAG index and schema graph** for additional context:
  - Docgen is only allowed to run when the file is **up-to-date in the LLMC RAG database**.
  - The enriched graph data will be fed **deterministically** into the docgen prompt.

This module does **not** dictate the exact LLM provider; it defines a contract and harness so providers can be swapped via config while preserving behavior and format.

## 2. Triggering and lifecycle (daemon + CLI/TUI)

### 2.1 Triggers

- **Daemon-driven (primary)**:
  - The LLMC RAG daemon (`llmc-rag-daemon`) manages a fleet of repos (`RepoDescriptor`).
  - For each repo, after core RAG indexing and enrichment reach a stable state, the daemon can schedule **docgen jobs** for eligible files.
  - Docgen jobs are executed via the existing job runner (`llmc-rag-job`), which will invoke a new docgen entrypoint (Python CLI or subcommand) inside the repo.

- **Manual / interactive (secondary)**:
  - TUI / CLI / MCP may expose commands like:
    - `llmc docs gen <relative_path>`
    - or a TUI action “Generate docs for this file”.
  - All interactive paths call into the **same docgen service** used by daemon jobs, honoring the same `llmc.toml` configuration and gating rules.

### 2.2 Single-concurrency gate for docgen

To avoid overwhelming external providers (Gemini, APIs, or TUIs) and to control cost:

- At any given time, **only one docgen operation per repo** is allowed to run.
- Sources of enforcement:
  - **Daemon side**:
    - Job runner must ensure that, for a given repo, docgen work is scheduled as a **serial stage** rather than as many parallel per-file jobs.
    - We will treat docgen as a **single batch docgen job** that internally iterates files one by one.
  - **Docgen service side**:
    - Within a process, a **per-repo mutex / lock** (e.g. `DocgenLock[repo_root]`) ensures that only one docgen batch runs at a time.
    - Interactive commands respect this lock; if docgen is already running, they either:
      - fail fast with a clear message, or
      - enqueue behind the current run (policy TBD, default: fail fast).

Result: even if the daemon loops quickly and multiple triggers happen, docgen will at most have a single active docgen batch per repo, and within that batch, files are processed **strictly sequentially**.

## 3. Configuration in llmc.toml

Docgen is configured via a new section in `llmc.toml`:

```toml
[docs.docgen]
enabled = true                # master toggle
backend = "shell"             # "shell" | "llmc_llm" | "http" | "mcp"
output_dir = "DOCS/REPODOCS"  # relative to repo_root

## Gate: docgen only runs after RAG index is fresh enough.
## (Implementation uses RAG DB and/or freshness indicators; see §4.)
require_rag_fresh = true

[docs.docgen.shell]
script = "scripts/gemini_docgen.sh"
args = ["--model", "gemini-1.5-pro", "--temperature", "0.0"]
timeout_seconds = 120

[docs.docgen.llmc_llm]
provider = "gemini"           # e.g. "gemini", "ollama", "gateway"
model = "gemini-1.5-pro"
temperature = 0.0
top_p = 0.0
top_k = 1
max_output_tokens = 4096

[docs.docgen.http]
url = "https://example.com/docgen"
method = "POST"
timeout_seconds = 120

[docs.docgen.mcp]
server = "docgen"             # MCP server id
tool = "generate_docs"        # tool name within that server
timeout_seconds = 120
```

Notes:

- There is exactly **one docgen backend per repo**; all entrypoints share this behavior.
- Environments may override via env vars (future extension, e.g. `LLMC_DOCGEN_BACKEND`).
- The **Gemini-backed shell script** is the initial implementation (`backend = "shell"`).

## 4. Gating rules (SHA + RAG freshness)

Docgen must only run when both of the following are satisfied:

1. **SHA gate (idempotence, orchestrator-side)**:
   - For each candidate source file:
     - Compute `file_sha256` from the current file contents.
     - Locate the documentation file:
       - `doc_path = repo_root / output_dir / (relative_path + ".md")`.
     - If `doc_path` exists:
       - Read first line; if it starts with `SHA256:` and the hash equals `file_sha256`:
         - **Skip docgen** for this file (no backend call).
     - If there is no doc or the hash differs:
       - File is **eligible** for docgen work.
   - This gate is performed in LLMC orchestration code (daemon/CLI), **before** invoking any backend or shell script. The backend no longer needs to compute or compare the hash.

2. **RAG freshness gate (graph/context availability)**:
   - Docgen should only run when the file is **up-to-date in the LLMC RAG database**, ensuring:
     - The current version of the file has been indexed.
     - Schema graph / call graph data reflects this version.
   - Implementation concept:
     - Use existing RAG DB (`tools.rag.database.Database`) and graph artifacts (`.llmc/rag_graph.json`) to determine:
       - Whether the file path exists in `files` table with `file_hash == file_sha256`.
       - Whether there are spans/entities referencing this file in `spans` / graph indices.
   - Policy:
     - If the file is **not yet indexed** or appears stale relative to `file_sha256`:
       - Docgen **skips** this file and records a reason (e.g. `SKIP_NOT_INDEXED`).
     - Only files that pass both SHA and RAG freshness gates are sent to the docgen backend.

## 5. Backend abstraction and interfaces

### 5.1 Python interfaces

Docgen is accessed via a small, explicit interface:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

@dataclass
class DocgenResult:
    status: str              # "noop" | "generated" | "skipped"
    sha256: str
    output_markdown: str | None  # present only when generated
    reason: str | None = None    # optional cause for "skipped"


class DocgenBackend(Protocol):
    def generate_for_file(
        self,
        repo_root: Path,
        relative_path: Path,
        *,
        file_sha256: str,
        source_contents: str,
        existing_doc_contents: str | None,
        graph_context: str | None,
    ) -> DocgenResult:
        ...
```

- All concrete backends implement `DocgenBackend`.
- The **orchestrator** is responsible for:
  - SHA gating (skip when hashes match).
  - RAG freshness gating.
  - Building `graph_context` (§6).
  - Reading and passing `existing_doc_contents` (if any).

### 5.2 Backend factory from config

Module (proposed): `llmc/docgen/config.py`

```python
from pathlib import Path
from typing import Any, Mapping

from .types import DocgenBackend


def load_docgen_backend(
    repo_root: Path,
    toml_data: Mapping[str, Any],
) -> DocgenBackend | None:
    """
    Read [docs.docgen] from llmc.toml and construct the appropriate backend.

    Returns None if docgen is disabled.
    Raises DocgenConfigError on invalid config.
    """
```

- Looks at `toml_data["docs"]["docgen"]`:
  - If `enabled` is false or section missing → returns `None`.
  - Dispatches on `backend`:
    - `"shell"` → `ShellDocgenBackend`.
    - `"llmc_llm"` → `LLMDocgenBackend`.
    - `"http"` → `HttpDocgenBackend`.
    - `"mcp"` → `McpDocgenBackend`.

### 5.3 Shell backend (Gemini script)

Module (proposed): `llmc/docgen/backends/shell_backend.py`

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ShellDocgenBackend:
    script: Path
    args: list[str]
    timeout_seconds: int

    def generate_for_file(
        self,
        repo_root: Path,
        relative_path: Path,
        *,
        file_sha256: str,
        source_contents: str,
        existing_doc_contents: str | None,
        graph_context: str | None,
    ) -> DocgenResult:
        ...
```

Behavior:

- Build a deterministic subprocess command, e.g.:

  - `cmd = [script, str(relative_path)] + args`
  - Environment variables or stdin carry the structured payload:
    - `repo_root`, `file_sha256`, `source_contents`, `existing_doc_contents`, `graph_context`.

- The shell script (e.g. `scripts/gemini_docgen.sh`) is responsible for:
  - Calling Gemini with:
    - Fixed model parameters (`temperature=0.0`, `top_p=0.0`, `top_k=1`, fixed `max_output_tokens`).
    - A **static system prompt** that encodes:
      - The doc format;
      - The SHA header rule;
      - The use of `graph_context`.
  - Returning either:
    - `NO-OP: SHA unchanged (<hash>)`, or
    - A Markdown document starting with `SHA256: <file_sha256>`.

- The backend validates the response:
  - If it starts with `NO-OP:` → `status="noop"`.
  - Else:
    - First line must start with `SHA256:` and match `file_sha256`; otherwise error.
    - `status="generated"`, `output_markdown=stdout`.

Docgen file writing is handled by the orchestrator / service, not by the shell script, to keep concerns separated.

## 6. Graph / RAG context feeding (deterministic)

For files that pass SHA and RAG gates, docgen receives **graph-enriched context**. This is derived from LLMC’s schema graph and enrichment DB:

- Implementation module: likely `tools.rag.graph_index`, `tools.rag.graph`, and helpers in `tools.rag.graph_enrich`.
- Context construction:
  - Given `repo_root` and `relative_path`:
    - Load graph indices from `.llmc/rag_graph.json` (via `graph_index.load_indices`).
    - Identify entities and relations associated with this file:
      - Where this file appears as a path for entities/nodes.
      - Where it appears in `where-used` / `lineage` queries.
    - Optionally merge enrichment snippets for relevant entities (`graph_enrich.enrich_graph_entities`).
  - Normalize into a deterministic, text-only payload, e.g.:

    ```text
    === GRAPH_CONTEXT_BEGIN ===
    indexed_at: <iso_timestamp>
    file: <relative_path>
    entities:
      - id: <entity_id>
        kind: <kind>
        name: <symbol_or_node_name>
        path: <repo_relative_path>
        span: <start_line>-<end_line>
        metadata_summary: <selected enrichment fields, if any>
    relations:
      - src: <entity_id>
        edge: <edge_type>  # CALLS / USES / etc.
        dst: <entity_id>
        path: <file_path_of_relation>
    === GRAPH_CONTEXT_END ===
    ```

- The same `graph_context` string is passed to **all backends** and is part of the deterministic input set.
- If graph data is missing or unusable for a file that otherwise passes SHA gate:
  - Behavior is configurable (initial default: **skip docgen** and record a `SKIP_NO_GRAPH` reason, to keep semantics “docgen only when graph is available”).

## 7. Orchestrator flow per file (within a batch)

Within a single docgen batch (daemon job or CLI command), the per-file flow is:

1. Discover candidate files (e.g. via RAG DB or `git ls-files` + suffix filters).
2. For each file, sequentially:
   1. Compute `file_sha256`.
   2. Resolve `doc_path` and read `existing_doc_contents` if present.
   3. **SHA gate**:
      - If doc exists and `SHA256:` matches `file_sha256` → mark `status="noop"`, skip backend.
   4. **RAG freshness gate**:
      - Ensure RAG DB and graph know about this file at `file_sha256`.
      - If not fresh → mark `status="skipped"` with reason (e.g. `SKIP_NOT_INDEXED`), skip backend.
   5. Build `graph_context` string from graph indices / enrichment.
   6. Invoke `backend.generate_for_file(...)`.
   7. If backend returns `status="generated"`:
      - Write doc to `doc_path` atomically (tmp file + rename).
   8. Record metrics/logging:
      - `"DOCGEN GENERATED <relative_path> <sha>"`
      - `"DOCGEN NOOP <relative_path> <sha>"`
      - `"DOCGEN SKIP <relative_path> <reason>"`

The batch-level controller will also enforce the **single-concurrency gate** per repo.

## 8. Testing and change risk

### 8.1 Test strategy

Unit / service tests (Python-level):

- **Config loading**:
  - Validate `load_docgen_backend` behavior for:
    - Missing `[docs.docgen]` section.
    - Enabled with each backend type.
    - Invalid values (e.g. bad backend name).

- **SHA + RAG gating**:
  - Given a temporary repo with:
    - A RAG DB where `files.path` and `file_hash` match the test file.
    - A doc file whose `SHA256:`:
      - matches the source hash → docgen skipped before backend.
      - does not match → backend is called.

- **Graph context assembly**:
  - Use a small synthetic `.llmc/rag_graph.json` and ensure `graph_context` includes expected entities/relations for a file.

- **Shell backend integration (mocked)**:
  - Replace the external script with a stub that:
    - Echoes a deterministic NO-OP line.
    - Echoes a deterministic doc with correct SHA line.
    - Echoes malformed outputs.
  - Verify that:
    - NO-OP returns `status="noop"` and no file writes.
    - Valid doc returns `status="generated"` and writes content as-is.
    - Malformed output causes an error.

Daemon / job tests (lightweight):

- When running a `llmc-rag-job` on a test repo with docgen enabled:
  - Ensure only **one docgen batch per repo** runs at a time, even if multiple daemon ticks are invoked quickly.
  - Ensure doc files are created only for files that:
    - have changed since last docgen, and
    - are present/fresh in RAG DB and graph.

### 8.2 Change risk

- New code touches:
  - Docgen service modules (`llmc/docgen/...`),
  - RAG-aware helpers to fetch graph context,
  - Daemon job runner wiring for docgen stage.
- Existing core RAG indexing / embedding code is mostly consumed, not modified.
- Main risks:
  - Misconfigured docgen leading to silent skips (must log clearly).
  - Overly strict RAG freshness gate causing docgen to never run (must be observable via logs / metrics).
  - Shell backend misbehavior (script path issues, timeouts).

Mitigations:

- Fail loud on invalid `llmc.toml` docgen config.
- Emit structured logs / metrics for:
  - docgen start/end,
  - per-file status,
  - backend failures.
- Keep single-concurrency gate simple (per-repo lock + serial batch processing).

