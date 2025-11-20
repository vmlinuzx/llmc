# SDD — Graph Import Resolution for Python Call Edges

## 1. Scope

This SDD covers the P0 fix for “orphaned” definition nodes caused by imported function calls being mis-attributed to the importing module in the schema graph. Example: `scripts/qwen_enrich_batch.py` calls `estimate_tokens_from_text` imported from `router`, but the graph currently creates an edge to `sym:qwen_enrich_batch.estimate_tokens_from_text` instead of `sym:router.estimate_tokens_from_text`.

In scope:

- Update Python AST extraction (`PythonSchemaExtractor` in `tools/rag/schema.py`) to maintain a per-module import map and use it when resolving call targets.
- Ensure call edges for imported functions and modules point to the correct definition entities when they exist.
- Add tests to lock this behavior and guard against regressions.
- Basic support for common, explicit import patterns:
  - `from module import func`
  - `from module import func as alias`
  - `import module`
  - `import module as alias`
  - Calls via imported module aliases (e.g., `module.func()` / `alias.func()`).

Out of scope for this patch:

- Full static name resolution (no flow analysis, no type inference).
- Wildcard imports (`from module import *`) and complex relative imports beyond level 0.
- Fixing method dispatch (e.g., `self.method()` → class method entity) or attribute chains deeper than `module.func`.
- Non-Python languages and Tree-sitter-based extraction, if any.

## 2. Responsibilities

- `PythonSchemaExtractor`:
  - Owns module-level import mapping (`self.import_map`) for the file being parsed.
  - Interprets import statements into a map from local names/aliases to fully-qualified module or symbol names.
  - Resolves call targets using this map before falling back to local module names.
- `extract_schema_from_file`:
  - Unchanged at the interface level; continues to call `PythonSchemaExtractor.extract`.
  - Gains more accurate `Relation(edge="calls")` targets for Python files.
- Graph builder (`build_enriched_schema_graph` / `build_graph_for_repo`):
  - No behavioral change beyond receiving higher-quality call edges.
- New tests:
  - Prove that imported functions produce edges to the defining module’s symbol, and that phantom “local stub” targets are no longer created for these cases.

## 3. Design Overview

### 3.1 Import Map

Extend `PythonSchemaExtractor.__init__` to create a file-scoped import table:

```python
self.import_map: Dict[str, str] = {}
```

This table maps:

- Local name → fully qualified module or symbol.

Examples:

- `from router import estimate_tokens_from_text`  
  → `self.import_map["estimate_tokens_from_text"] = "router.estimate_tokens_from_text"`
- `from router import estimate_tokens_from_text as est`  
  → `self.import_map["est"] = "router.estimate_tokens_from_text"`
- `import router`  
  → `self.import_map["router"] = "router"`
- `import router as rt`  
  → `self.import_map["rt"] = "router"`
- `import package.module as mod`  
  → `self.import_map["mod"] = "package.module"`

We do not add entries for wildcard imports or imports whose module cannot be determined (e.g., level>0 relative imports) in this first increment.

### 3.2 Import Recording

Add two private helper methods to `PythonSchemaExtractor`:

```python
def _record_import(self, node: ast.Import) -> None: ...
def _record_import_from(self, node: ast.ImportFrom) -> None: ...
```

Semantics:

- `_record_import`:
  - For each `alias` in `node.names`:
    - `module_name = alias.name` (e.g., `"router"`, `"package.module"`).
    - `local_name = alias.asname or module_name`.
    - `self.import_map[local_name] = module_name`.

- `_record_import_from`:
  - Ignore relative imports with `node.level > 0` for now (non-goal).
  - For each `alias` in `node.names`:
    - Skip `alias.name == "*"`.
    - `base = node.module` (string or None; we only handle non-None absolute modules).
    - `symbol = alias.name` (e.g., `"estimate_tokens_from_text"`).
    - `local_name = alias.asname or symbol`.
    - `self.import_map[local_name] = f"{base}.{symbol}"`.

These helpers interpret import statements into a normalization that downstream call resolution can use.

### 3.3 Module Visit Order

Update `visit_module` to populate the import map before walking functions and classes:

Current:

```python
def visit_module(self, node: ast.Module):
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            self.visit_function(item)
        elif isinstance(item, ast.ClassDef):
            self.visit_class(item)
```

Proposed:

```python
def visit_module(self, node: ast.Module):
    # First pass: collect imports
    for item in node.body:
        if isinstance(item, ast.Import):
            self._record_import(item)
        elif isinstance(item, ast.ImportFrom):
            self._record_import_from(item)

    # Second pass: collect entities and relations
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            self.visit_function(item)
        elif isinstance(item, ast.ClassDef):
            self.visit_class(item)
```

We intentionally ignore import statements inside functions or classes for now. If needed later, we can extend the design to allow nested scopes with their own import maps.

### 3.4 Call Target Resolution

Introduce a helper responsible for mapping raw callee names into `sym:` IDs:

```python
def _resolve_callee_symbol(self, callee: str) -> str:
    """
    Return a fully qualified symbol name (without 'sym:' prefix)
    for the given callee, using import_map when possible.
    Fallback: treat callee as local to this module.
    """
```

Resolution rules:

1. If `callee` contains a dot (e.g., `"router.estimate_tokens_from_text"` or `"alias.func"`):
   - Split once: `prefix, suffix = callee.split(".", 1)`.
   - If `prefix` is in `self.import_map`:
     - `target = self.import_map[prefix]` (e.g., `"router"` or `"package.module"`).
     - Return `f"{target}.{suffix}"`.
   - Else:
     - Fall back to local: `return f"{self.module_name}.{callee}"`.

2. If `callee` is a bare name (e.g., `"estimate_tokens_from_text"`):
   - If `callee in self.import_map`:
     - Return `self.import_map[callee]` (e.g., `"router.estimate_tokens_from_text"`).
   - Else:
     - Fall back to local: `return f"{self.module_name}.{callee}"`.

3. We keep this logic intentionally simple; attribute chains deeper than one dot that are *not* module aliases are treated as local (`self.module_name.callee`), matching current behavior for things like `obj.method()`.

Update `visit_call` to use this helper:

Current:

```python
if callee_name:
    callee_id = f"sym:{self.module_name}.{callee_name}"
    self.relations.append(
        Relation(src=caller_id, edge="calls", dst=callee_id)
    )
```

Proposed:

```python
if callee_name:
    symbol = self._resolve_callee_symbol(callee_name)
    callee_id = f"sym:{symbol}"
    self.relations.append(
        Relation(src=caller_id, edge="calls", dst=callee_id)
    )
```

With the change, in `scripts/qwen_enrich_batch.py`:

- Import: `from router import estimate_tokens_from_text`  
  → `self.import_map["estimate_tokens_from_text"] = "router.estimate_tokens_from_text"`.
- Call: `estimate_tokens_from_text(prompt)`  
  → `callee_name = "estimate_tokens_from_text"`  
  → `_resolve_callee_symbol` → `"router.estimate_tokens_from_text"`  
  → `dst = "sym:router.estimate_tokens_from_text"`.

This gives the desired edge from the importer to the router definition entity.

## 4. File-Level Changes

### 4.1 `tools/rag/schema.py`

**New fields in `PythonSchemaExtractor.__init__`:**

- `self.import_map: Dict[str, str] = {}`.

**New private helpers:**

- `_record_import(self, node: ast.Import) -> None`
- `_record_import_from(self, node: ast.ImportFrom) -> None`
- `_resolve_callee_symbol(self, callee: str) -> str`

**Updated methods:**

- `visit_module`:
  - Two-pass traversal (imports, then definitions).
- `visit_call`:
  - Uses `_resolve_callee_symbol` to compute `callee_id`.
  - No change to `Relation` structure (still `Relation(src, "calls", dst)`).

No changes to public functions (`extract_schema_from_file`, `build_enriched_schema_graph`, `build_graph_for_repo`) besides observing the improved call edges.

### 4.2 New Tests

Add a new test module:

- `tools/rag/tests/test_python_import_resolution.py`

Proposed tests:

1. **Simple imported function**

   ```python
   def test_imported_function_call_targets_definer(tmp_path):
       repo_root = tmp_path / "repo"
       repo_root.mkdir()

       definer = repo_root / "definer.py"
       definer.write_text(
           "def hello():
"
           "    pass
",
           encoding="utf-8",
       )

       importer = repo_root / "importer.py"
       importer.write_text(
           "from definer import hello
"
           "
"
           "def caller():
"
           "    hello()
",
           encoding="utf-8",
       )

       graph = build_graph_for_repo(repo_root, require_enrichment=False)

       calls = [
           (rel.src, rel.dst)
           for rel in graph.relations
           if rel.edge == "calls"
       ]

       assert ("sym:importer.caller", "sym:definer.hello") in calls
       # Guardrail: no phantom local stub
       assert ("sym:importer.caller", "sym:importer.hello") not in calls
   ```

2. **Module alias call**

   ```python
   def test_module_alias_call_resolves_via_import_map(tmp_path):
       repo_root = tmp_path / "repo"
       repo_root.mkdir()

       definer = repo_root / "definer.py"
       definer.write_text(
           "def hello():
"
           "    pass
",
           encoding="utf-8",
       )

       importer = repo_root / "importer.py"
       importer.write_text(
           "import definer as d
"
           "
"
           "def caller():
"
           "    d.hello()
",
           encoding="utf-8",
       )

       graph = build_graph_for_repo(repo_root, require_enrichment=False)

       calls = [
           (rel.src, rel.dst)
           for rel in graph.relations
           if rel.edge == "calls"
       ]

       assert ("sym:importer.caller", "sym:definer.hello") in calls
   ```

3. **Alias for imported function**

   ```python
   def test_imported_function_alias_resolves(tmp_path):
       repo_root = tmp_path / "repo"
       repo_root.mkdir()

       definer = repo_root / "definer.py"
       definer.write_text(
           "def hello():
"
           "    pass
",
           encoding="utf-8",
       )

       importer = repo_root / "importer.py"
       importer.write_text(
           "from definer import hello as hi
"
           "
"
           "def caller():
"
           "    hi()
",
           encoding="utf-8",
       )

       graph = build_graph_for_repo(repo_root, require_enrichment=False)

       calls = [
           (rel.src, rel.dst)
           for rel in graph.relations
           if rel.edge == "calls"
       ]

       assert ("sym:importer.caller", "sym:definer.hello") in calls
   ```

These tests use the existing public `build_graph_for_repo` API and therefore exercise `extract_schema_from_file` and `PythonSchemaExtractor` in a realistic way.

Optionally, add a focused unit test that instantiates `PythonSchemaExtractor` directly on a small snippet and inspects `extract()` to validate `self.import_map` behavior, but the integration tests above should be sufficient for this P0.

## 5. Risks and Limitations

- **Relative imports:**  
  This patch ignores `from .foo import bar` and other relative imports with `level > 0`. Those calls will still be treated as local. Future work can add a `module_package` concept to compute fully qualified module names based on file paths.

- **Wildcard imports:**  
  `from module import *` is not resolved. Calls to names that come only from wildcard imports will still be treated as local.

- **Non-import attribute calls:**  
  We cannot distinguish `obj.method()` where `obj` is an imported module alias vs. a regular variable without control-flow or type analysis. The design here resolves `prefix.suffix` via `import_map` only when `prefix` is a known imported name, which keeps behavior safe and predictable.

- **Performance:**  
  Added overhead is minimal (two linear passes over the module body + constant-time map lookups in `visit_call`). This should be negligible compared to AST parsing and graph construction.

- **Partial improvements:**  
  This patch addresses the immediate P0 issue (lost graph linkage for imported functions like `estimate_tokens_from_text`) but does not attempt full Python name resolution. Additional passes (e.g., resolving method calls on `self`, module-level re-exports, etc.) can be layered on top in future increments.

## 6. Acceptance Criteria

- In the **current LLMC repo**, after rebuilding the graph:

  - `router.py` is no longer reported as an orphan in `rag inspect` / equivalent tooling; it has at least one incoming `calls` edge from `scripts/qwen_enrich_batch.py` and any other importers of its functions.
  - There is no edge whose `dst` is `sym:qwen_enrich_batch.estimate_tokens_from_text` (or similar phantom local symbols) when the actual definition exists in `router.py`.

- New tests in `tools/rag/tests/test_python_import_resolution.py` pass and are stable.

- Existing graph-related tests:
  - `tools/rag/tests/test_build_graph_for_repo.py`
  - `tools/rag/tests/test_graph_json_sanity.py`
  - `tools/rag/tests/test_schema_enriched_graph.py`

  continue to pass without modification.

- No regressions are observed in RAG Nav behavior that depends on call edges (e.g., “Used By” queries in `rag where_used` once Phase 3 is wired).