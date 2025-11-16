# Implementation SDD — LLMC RAG Nav Task 2: Graph Builder & CLI

## 1. Modules and Functions

### 1.1 `tools.rag_nav.tool_handlers`

- Constants:
  - `GRAPH_FILENAME = "rag_graph.json"`
  - `DEFAULT_SCHEMA_VERSION = "1"`

- `_graph_path(repo_root: Path) -> Path`
  - Returns `${repo_root}/.llmc/rag_graph.json` by deriving the
    directory from `status_path(repo_root).parent`.

- `_detect_git_head(repo_root: Path) -> Optional[str]`
  - Runs `git -C <repo_root> rev-parse HEAD`.
  - Returns SHA string on success; `None` on failure.

- `_write_graph_artifact(repo_root: Path, data: dict) -> Path`
  - Writes `data` as pretty-printed JSON to a temp file in `.llmc/`,
    then atomically replaces `rag_graph.json`.
  - Ensures `.llmc/` exists.

- `_discover_source_files(repo_root: Path) -> list[str]`
  - Walks the repo root with `os.walk`.
  - Skips directories: `.git`, `.llmc`, `.venv`, `__pycache__`.
  - Includes files ending with `.py` only.
  - Returns sorted relative paths as strings.

- `build_graph_for_repo(repo_root: Path) -> IndexStatus`
  - Resolves `repo_root` to an absolute path.
  - Calls `_discover_source_files` to get a file list.
  - Builds `graph_payload` dict with `repo`, `schema_version`,
    `generated_at`, and `files`.
  - Calls `_write_graph_artifact` to persist it.
  - Calls `_detect_git_head` to get `last_indexed_commit` (if any).
  - Constructs `IndexStatus` with:
    - `index_state="fresh"`
    - `last_indexed_at` = `generated_at`
    - `schema_version=DEFAULT_SCHEMA_VERSION`
  - Calls `save_status(repo_root, status)`.
  - Returns the `IndexStatus` instance.

### 1.2 `tools.rag_nav.cli`

- `_parse_args(argv: list[str]) -> argparse.Namespace`
  - Defines the `build-graph` and `status` subcommands and their
    arguments.

- `cmd_build_graph(repo: Path) -> int`
  - Resolves repo path and invokes `build_graph_for_repo`.
  - Prints a short human-readable summary of the resulting status.

- `cmd_status(repo: Path, as_json: bool) -> int`
  - Loads status via `load_status`.
  - If `as_json` is True:
    - Prints a JSON object or `null` if no status.
  - Otherwise:
    - Prints human-readable fields, including the status file path.

- `main(argv: list[str] | None = None) -> int`
  - Entry point used by both `python -m tools.rag_nav.cli` and the
    `scripts/llmc-rag-nav` wrapper.
  - Dispatches to the appropriate command handler.

### 1.3 `scripts/llmc-rag-nav`

- Thin bash wrapper:

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  python -m tools.rag_nav.cli "$@"
  ```

- Allows simple usage from the repo root without worrying about
  Python module invocation.

## 2. Error Handling and Edge Cases

- If git is unavailable or the directory is not a git repo,
  `_detect_git_head` returns `None` and `IndexStatus.last_indexed_commit`
  is set to `None`.
- If `.llmc/` cannot be created or written, `_write_graph_artifact` will
  raise an `OSError`, causing `build_graph_for_repo` to fail. This is
  appropriate, as the caller likely wants to treat this as fatal.
- The CLI uses exit codes (0 on success, 1 on unexpected command).

## 3. Integration and Dependencies

- Depends only on modules from Task 1:
  - `tools.rag_nav.metadata` (`status_path`, `save_status`, `load_status`)
  - `tools.rag_nav.models` (`IndexStatus`)
- Does not depend on the main RAG daemon or external services.
- Does not yet implement where-used or lineage traversal.

## 4. Testing Details

- `tests/test_rag_nav_build_graph.py`
  - Uses `tmp_path` to construct a fake repo.
  - Writes `module_a.py` at the root and `pkg/module_b.py` in a subdir.
  - Calls `build_graph_for_repo(tmp_path)`.
  - Asserts:
    - `load_status(tmp_path)` is not `None`.
    - `index_state == "fresh"`.
    - `schema_version == "1"`.
    - Graph file exists.
    - JSON payload contains the expected relative file paths.

