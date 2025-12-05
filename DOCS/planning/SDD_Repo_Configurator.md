# Software Design Document: Repo Configurator

**Status:** Ready for Implementation  
**Version:** 1.0  
**Date:** 2025-12-03  
**Owner:** Core Team  
**Encoding:** LATIN-1 (ASCII-only content)

---

## 1. Overview

The Repo Configurator generates a per-repository `llmc.toml` configuration file during the `llmc-rag-repo add` onboarding flow. It uses an existing template (LLMC's own config or a user-provided file) as the source of truth, applies minimal edits, and preserves comments and formatting.

### 1.1 Key Design Decisions

- **Integration point:** Hooks into existing `tools/rag_repo/cli.py::_cmd_add()`, not a new service abstraction.
- **Template-based:** Copies and minimally edits an existing `llmc.toml` as the golden source.
- **Comment preservation:** Uses `tomlkit` library to preserve comments and whitespace.
- **Minimal edits:** Only safe, predictable changes are applied (paths, optional overrides).
- **Safe handling:** Existing configs are handled conservatively with backups on replacement.
- **CI-friendly:** `--yes` flag suppresses prompts and never overwrites existing configs.

### 1.2 Prerequisites

**New dependency required:**

```
tomlkit>=0.12.0
```

Add to `pyproject.toml` or `requirements.txt` before implementation begins.

---

## 2. Scope

### 2.1 In Scope

- Generating `llmc.toml` when onboarding a repository with `llmc-rag-repo add`
- Using an existing template as base with minimal edits:
  - Update `mcp.tools.allowed_roots` to target repo root
  - Update `tool_envelope.workspace.root` to target repo root
  - Optionally append to `indexing.exclude_dirs`
  - Optionally adjust embeddings endpoint/model
  - Optionally adjust enrichment endpoint/model for default chain
- Interactive prompts for overriding configuration values
- Non-interactive mode (`--yes`) using template defaults
- Safe handling of existing `llmc.toml` (keep, replace with backup, or abort)

### 2.2 Out of Scope (v1)

- Automatic merging of existing configs with new templates
- Template library with named profiles (python-ml, typescript-web, etc.)
- Dedicated `validate` or `diff` commands
- Deep structural changes to enrichment chains
- Network connectivity validation

---

## 3. Architecture

### 3.1 Module Structure

All components reside in a single file for v1:

```
tools/rag_repo/configurator.py
```

This file contains:
- `ConfigOptions` dataclass
- `RepoConfigurator` class (orchestration)
- Template loading functions
- Option collection functions
- Config transformation functions
- Config writing functions

Single-file structure is intentional for this scope. Future versions may split into multiple modules if complexity warrants.

### 3.2 Component Overview

```
llmc-rag-repo add /path/to/repo [--yes] [--template FILE]
                |
                v
+-------------------------------------------------------+
|  _cmd_add() in tools/rag_repo/cli.py                  |
|                                                       |
|  1. inspect_repo()           <- existing              |
|  2. plan_workspace()         <- existing              |
|  3. init_workspace()         <- existing              |
|  4. validate_workspace()     <- existing              |
|  5. registry.register()      <- existing              |
|  6. ------------------------------------------------- |
|  |  NEW: RepoConfigurator.configure()               | |
|  |       - Load template                            | |
|  |       - Handle existing file (K/R/A)             | |
|  |       - Collect options (if interactive)         | |
|  |       - Transform config                         | |
|  |       - Write output                             | |
|  --------------------------------------------------- |
|  7. notify_refresh()         <- existing              |
+-------------------------------------------------------+
```

### 3.3 Data Structures

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ConfigOptions:
    """User-specified overrides and context for config generation."""
    repo_path: Path
    custom_embeddings_url: str | None = None
    custom_embeddings_model: str | None = None
    custom_enrichment_url: str | None = None
    custom_enrichment_model: str | None = None
    additional_excludes: list[str] = field(default_factory=list)
```

The `field(default_factory=list)` avoids the mutable default trap.

---

## 4. Detailed Design

### 4.1 CLI Integration

**File:** `tools/rag_repo/cli.py`

Add `--template` argument to the `add` subparser:

```python
p_add.add_argument(
    "--template",
    help="Path to custom llmc.toml template",
    default=None
)
```

Invoke configurator in `_cmd_add()` after workspace setup:

```python
from .configurator import RepoConfigurator

configurator = RepoConfigurator(interactive=not args.yes)
configurator.configure(repo_path=repo_path, template_path=args.template)
```

### 4.2 Template Discovery

Resolution order:

1. If `--template PATH` provided, use that exact file
2. Otherwise, search upward from `Path(__file__).resolve().parent` for `llmc.toml`
3. Optionally check `LLMC_ROOT` environment variable

**Failure modes:**

- Template file not found (user-provided or auto-discovered): abort with clear error message advising use of `--template`
- Template parse failure: abort with TOML error details

### 4.3 Template Loading

```python
import tomlkit

def load_template(template_path: Path) -> tomlkit.TOMLDocument:
    """Load and parse template, preserving comments."""
    text = template_path.read_text(encoding="utf-8")
    return tomlkit.parse(text)
```

Extract defaults for prompting:

```python
# Embeddings defaults
profile = doc["embeddings"]["profiles"]["docs"]
default_emb_url = profile.get("ollama", {}).get("api_base", "<unset>")
default_emb_model = profile.get("model", "<unset>")

# Enrichment defaults
default_chain_name = doc["enrichment"].get("default_chain", "<unset>")
# Find matching chain entries for URL/model display
```

### 4.4 Existing File Handling

**Target path:** `repo_path / "llmc.toml"`

**Interactive mode:**

If file exists, prompt user:

```
llmc.toml already exists at /path/to/repo/llmc.toml

  (K)eep existing config and skip generation
  (R)eplace with new config (backup will be created)
  (A)bort onboarding

Choice [K/R/A]:
```

Behavior:
- **K (Keep):** Print message, skip config generation, continue onboarding
- **R (Replace):** Rename existing to `llmc.toml.bak.YYYYMMDDHHMMSS`, proceed with generation
- **A (Abort):** Exit `_cmd_add` with non-zero status

**Non-interactive mode (`--yes`):**

If file exists:
- Print message to stderr: "llmc.toml exists, skipping generation"
- Do not modify existing file
- Continue with remaining onboarding steps

**EOFError handling:**

```python
try:
    choice = input("Choice [K/R/A]: ").strip().upper()
except EOFError:
    choice = "A"  # Treat EOF as abort
```

### 4.5 Option Collection

**Interactive mode prompts:**

1. **Embeddings:**
   ```
   Embeddings API
     Default URL:   http://192.168.5.20:11434
     Default model: nomic-embed-text
   
   Use defaults? [Y/n]:
   ```
   If no, prompt for URL and model.

2. **Enrichment:**
   ```
   Enrichment LLM
     Default chain: athena
     URL:           http://192.168.5.20:11434
     Model:         ministral-14b (+ fallbacks)
   
   Use defaults? [Y/n]:
   ```
   If no, prompt for URL and model. All entries in the default chain are updated.

3. **Exclude directories:**
   ```
   Additional directories to exclude from indexing
   (comma-separated, or press Enter for none):
   ```

**Non-interactive mode:**

- No prompts
- `ConfigOptions` uses template defaults
- `additional_excludes` remains empty

### 4.6 Config Transformation

Operating on the parsed `tomlkit.TOMLDocument`:

#### 4.6.1 Path Substitution

```python
import tomlkit

def ensure_nested_table(doc, *keys):
    """Ensure nested tables exist, creating if needed."""
    current = doc
    for key in keys:
        if key not in current:
            current.add(key, tomlkit.table())
        current = current[key]
    return current

# Set allowed_roots
mcp_tools = ensure_nested_table(doc, "mcp", "tools")
mcp_tools["allowed_roots"] = [str(repo_path)]

# Set workspace root
te_workspace = ensure_nested_table(doc, "tool_envelope", "workspace")
te_workspace["root"] = str(repo_path)
```

Note: Use `doc.add(key, tomlkit.table())` rather than `doc[key] = tomlkit.table()` to preserve document structure and insertion order.

#### 4.6.2 Embeddings Override (Optional)

If `ConfigOptions` contains custom values:

```python
if options.custom_embeddings_url or options.custom_embeddings_model:
    profile = doc["embeddings"]["profiles"]["docs"]
    if options.custom_embeddings_url:
        profile["ollama"]["api_base"] = options.custom_embeddings_url
    if options.custom_embeddings_model:
        profile["model"] = options.custom_embeddings_model
```

Only the "docs" profile is modified in v1.

#### 4.6.3 Enrichment Override (Optional)

If `ConfigOptions` contains custom values:

```python
if options.custom_enrichment_url or options.custom_enrichment_model:
    default_chain = doc["enrichment"].get("default_chain")
    if default_chain:
        for entry in doc["enrichment"]["chain"]:
            if entry.get("chain") == default_chain:
                if options.custom_enrichment_url:
                    entry["url"] = options.custom_enrichment_url
                if options.custom_enrichment_model:
                    entry["model"] = options.custom_enrichment_model
    else:
        # Log warning: default chain not found, skipping enrichment override
        pass
```

All entries matching the default chain are updated as a group.

#### 4.6.4 Indexing Excludes (Optional)

```python
if options.additional_excludes:
    indexing = ensure_nested_table(doc, "indexing")
    if "exclude_dirs" not in indexing:
        indexing.add("exclude_dirs", tomlkit.array())
    
    existing = set(indexing["exclude_dirs"])
    for pattern in options.additional_excludes:
        if pattern not in existing:
            indexing["exclude_dirs"].append(pattern)
```

### 4.7 Config Writing

**Atomic write required** to prevent corrupted configs if process dies mid-write:

```python
import tempfile
from datetime import datetime, timezone

def write_config(doc: tomlkit.TOMLDocument, repo_path: Path, template_path: Path):
    """Write config atomically with header comment."""
    
    # Build header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        "# Generated by: llmc-rag-repo add\n"
        f"# Generated on: {timestamp}\n"
        f"# Template: {template_path}\n"
        "#\n"
    )
    
    # Serialize
    body = tomlkit.dumps(doc)
    output = header + "\n" + body
    
    # Atomic write: write to temp file, then rename
    target = repo_path / "llmc.toml"
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=repo_path,
        delete=False,
        suffix='.tmp',
        encoding='utf-8'
    ) as f:
        f.write(output)
        tmp_path = Path(f.name)
    
    tmp_path.rename(target)
```

**Backup naming:**

```python
from datetime import datetime

def backup_path(target: Path) -> Path:
    """Generate timestamped backup path."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return target.with_suffix(f".toml.bak.{ts}")
```

---

## 5. Error Handling

| Condition | Behavior |
|-----------|----------|
| Template file not found | Abort with message advising `--template` |
| Template parse failure | Abort with TOML error details |
| Missing sections in template | Create with minimal defaults |
| Default chain not found | Log warning, skip enrichment override |
| Permission denied (read/write) | Abort with permission error message |
| User chooses Abort | Exit `_cmd_add` with non-zero status |
| EOFError on input() | Treat as Abort |

---

## 6. Testing Strategy

**Test location:** `tests/rag_repo/test_configurator.py`

Tests are written incrementally per phase, co-located with implementation.

### 6.1 Test Categories

1. **Template loading:**
   - Parse valid template with comments
   - Verify comments preserved in parsed doc
   - Handle missing template (expect error)
   - Handle invalid TOML (expect error)

2. **ConfigOptions:**
   - Default values correct
   - `additional_excludes` is fresh list per instance

3. **Option collection:**
   - Interactive: monkeypatch `input()`, verify overrides captured
   - Non-interactive: verify no prompts, defaults used

4. **Transformations:**
   - `allowed_roots` set to repo path
   - `workspace.root` set to repo path
   - Embeddings URL/model override applied
   - Enrichment entries updated (all matching default chain)
   - Exclude dirs appended without duplicates
   - Missing sections created

5. **Existing file handling:**
   - Keep: original unchanged, no new file
   - Replace: backup created, new file written
   - Abort: exception or non-zero return
   - Non-interactive with existing: skip, no modification

6. **Config writing:**
   - Header present with correct format
   - Comments from template preserved
   - Atomic write (verify temp file pattern)
   - Backup file exists after replace

7. **End-to-end:**
   - New repo: `llmc.toml` created with correct content
   - Existing repo: interactive and non-interactive branches
   - Integration with full `_cmd_add` flow

### 6.2 Test Fixtures

- Minimal template in `tests/data/minimal_template.toml`
- Template with comments in `tests/data/commented_template.toml`
- Use `tmp_path` pytest fixture for isolated test directories

---

## 7. Implementation Phases

### Phase 1: CLI Integration and Skeleton (Easy, ~1 hour)

**Tasks:**
- Add `tomlkit` to project dependencies
- Create `tools/rag_repo/configurator.py` with skeleton class
- Add `--template` argument to CLI
- Wire `RepoConfigurator` invocation in `_cmd_add()`

**Implementation:**

```python
# tools/rag_repo/configurator.py

from pathlib import Path

class RepoConfigurator:
    def __init__(self, interactive: bool = True):
        self.interactive = interactive
    
    def configure(self, repo_path: Path, template_path: Path | None = None) -> Path | None:
        """Generate llmc.toml for repo. Returns path or None if skipped."""
        print(f"[DEBUG] Configurator invoked for {repo_path}")
        return None  # Stub
```

**Tests:**
- CLI accepts `--template` without error
- Configurator is invoked (check debug output or mock)

---

### Phase 2: Template Discovery and Loading (Medium, ~1.5 hours)

**Tasks:**
- Implement template path resolution (user-provided or auto-discovery)
- Load and parse template with tomlkit
- Extract default values for prompting
- Handle missing/invalid template errors

**Implementation:**

```python
def _find_template(self, template_path: Path | None) -> Path:
    """Resolve template path."""
    if template_path is not None:
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {template_path}\n"
                "Provide a valid path with --template"
            )
        return template_path
    
    # Auto-discovery: walk up from this file
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        candidate = parent / "llmc.toml"
        if candidate.exists():
            return candidate
    
    raise FileNotFoundError(
        "Could not find llmc.toml template.\n"
        "Provide a template with --template /path/to/llmc.toml"
    )

def _load_template(self, template_path: Path) -> tomlkit.TOMLDocument:
    """Load and parse template."""
    try:
        text = template_path.read_text(encoding="utf-8")
        return tomlkit.parse(text)
    except tomlkit.exceptions.ParseError as e:
        raise ValueError(f"Invalid TOML in template: {e}")
```

**Tests:**
- Valid template loads and parses
- Comments preserved in parsed doc
- Missing template raises FileNotFoundError
- Invalid TOML raises ValueError

---

### Phase 3: Existing File Handling (Medium, ~1.5 hours)

**Tasks:**
- Check if `repo_path / "llmc.toml"` exists
- Interactive: prompt K/R/A with EOFError handling
- Non-interactive: skip if exists
- Implement timestamped backup

**Implementation:**

```python
def _handle_existing(self, target: Path) -> str:
    """
    Handle existing llmc.toml.
    
    Returns:
        "proceed" - continue with generation
        "skip" - skip generation, continue onboarding
        "abort" - abort onboarding
    """
    if not target.exists():
        return "proceed"
    
    if not self.interactive:
        print(f"llmc.toml exists at {target}, skipping generation", file=sys.stderr)
        return "skip"
    
    print(f"\nllmc.toml already exists at {target}\n")
    print("  (K)eep existing config and skip generation")
    print("  (R)eplace with new config (backup will be created)")
    print("  (A)bort onboarding\n")
    
    try:
        choice = input("Choice [K/R/A]: ").strip().upper()
    except EOFError:
        choice = "A"
    
    if choice == "K":
        print("Keeping existing config.")
        return "skip"
    elif choice == "R":
        backup = self._create_backup(target)
        print(f"Backed up to {backup}")
        return "proceed"
    else:
        return "abort"

def _create_backup(self, target: Path) -> Path:
    """Create timestamped backup of existing file."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = target.with_suffix(f".toml.bak.{ts}")
    target.rename(backup)
    return backup
```

**Tests:**
- No existing file: returns "proceed"
- Interactive Keep: original unchanged, returns "skip"
- Interactive Replace: backup created, returns "proceed"
- Interactive Abort: returns "abort"
- Non-interactive with existing: returns "skip", no modification
- EOFError treated as abort

---

### Phase 4: Option Collection (Medium, ~1.5 hours)

**Tasks:**
- Implement `ConfigOptions` dataclass
- Extract defaults from parsed template
- Interactive prompts for overrides
- Non-interactive uses defaults

**Implementation:**

```python
@dataclass
class ConfigOptions:
    repo_path: Path
    custom_embeddings_url: str | None = None
    custom_embeddings_model: str | None = None
    custom_enrichment_url: str | None = None
    custom_enrichment_model: str | None = None
    additional_excludes: list[str] = field(default_factory=list)

def _collect_options(self, repo_path: Path, doc: tomlkit.TOMLDocument) -> ConfigOptions:
    """Collect user options (interactive) or use defaults."""
    options = ConfigOptions(repo_path=repo_path)
    
    if not self.interactive:
        return options
    
    # Extract defaults from template
    emb_profile = doc.get("embeddings", {}).get("profiles", {}).get("docs", {})
    default_emb_url = emb_profile.get("ollama", {}).get("api_base", "<unset>")
    default_emb_model = emb_profile.get("model", "<unset>")
    
    # Prompt for embeddings
    print(f"\nEmbeddings API")
    print(f"  Default URL:   {default_emb_url}")
    print(f"  Default model: {default_emb_model}")
    
    try:
        use_default = input("\nUse defaults? [Y/n]: ").strip().lower()
    except EOFError:
        use_default = "y"
    
    if use_default in ("n", "no"):
        options.custom_embeddings_url = input("  URL: ").strip() or None
        options.custom_embeddings_model = input("  Model: ").strip() or None
    
    # Similar for enrichment...
    # Similar for exclude dirs...
    
    return options
```

**Tests:**
- Non-interactive: no prompts, defaults used
- Interactive with defaults: Enter accepts, no custom values
- Interactive with overrides: custom values captured
- Empty input treated as "use default"

---

### Phase 5: Config Transformation (Hard, ~2 hours)

**Tasks:**
- Path substitution (allowed_roots, workspace.root)
- Embeddings override
- Enrichment override (all entries matching default chain)
- Index excludes append
- Create missing sections as needed

**Implementation:**

```python
def _transform(self, doc: tomlkit.TOMLDocument, options: ConfigOptions) -> None:
    """Apply transformations to parsed doc in-place."""
    repo_str = str(options.repo_path)
    
    # Path substitution
    mcp_tools = self._ensure_table(doc, "mcp", "tools")
    mcp_tools["allowed_roots"] = [repo_str]
    
    te_workspace = self._ensure_table(doc, "tool_envelope", "workspace")
    te_workspace["root"] = repo_str
    
    # Embeddings override
    if options.custom_embeddings_url or options.custom_embeddings_model:
        try:
            profile = doc["embeddings"]["profiles"]["docs"]
            if options.custom_embeddings_url:
                if "ollama" not in profile:
                    profile.add("ollama", tomlkit.table())
                profile["ollama"]["api_base"] = options.custom_embeddings_url
            if options.custom_embeddings_model:
                profile["model"] = options.custom_embeddings_model
        except KeyError:
            pass  # Profile doesn't exist, skip
    
    # Enrichment override
    if options.custom_enrichment_url or options.custom_enrichment_model:
        enrichment = doc.get("enrichment", {})
        default_chain = enrichment.get("default_chain")
        if default_chain and "chain" in enrichment:
            for entry in enrichment["chain"]:
                if entry.get("chain") == default_chain:
                    if options.custom_enrichment_url:
                        entry["url"] = options.custom_enrichment_url
                    if options.custom_enrichment_model:
                        entry["model"] = options.custom_enrichment_model
    
    # Index excludes
    if options.additional_excludes:
        indexing = self._ensure_table(doc, "indexing")
        if "exclude_dirs" not in indexing:
            indexing.add("exclude_dirs", tomlkit.array())
        existing = set(indexing["exclude_dirs"])
        for pattern in options.additional_excludes:
            if pattern not in existing:
                indexing["exclude_dirs"].append(pattern)

def _ensure_table(self, doc, *keys) -> tomlkit.items.Table:
    """Ensure nested tables exist, creating with add() if needed."""
    current = doc
    for key in keys:
        if key not in current:
            current.add(key, tomlkit.table())
        current = current[key]
    return current
```

**Tests:**
- `allowed_roots` set correctly
- `workspace.root` set correctly
- Embeddings URL/model applied to docs profile
- Enrichment entries updated (verify all matching chain)
- Exclude dirs appended, no duplicates
- Missing sections created without error
- Missing default chain logs warning (or skips silently)

---

### Phase 6: Config Writing (Medium, ~1.5 hours)

**Tasks:**
- Build header comment
- Serialize with tomlkit
- Atomic write (temp file + rename)

**Implementation:**

```python
import tempfile
from datetime import datetime, timezone

def _write_config(
    self,
    doc: tomlkit.TOMLDocument,
    repo_path: Path,
    template_path: Path
) -> Path:
    """Write config atomically with header."""
    
    # Header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        "# Generated by: llmc-rag-repo add\n"
        f"# Generated on: {timestamp}\n"
        f"# Template: {template_path}\n"
        "#\n"
    )
    
    # Serialize
    body = tomlkit.dumps(doc)
    output = header + "\n" + body
    
    # Atomic write
    target = repo_path / "llmc.toml"
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=repo_path,
        delete=False,
        suffix='.tmp',
        encoding='utf-8'
    ) as f:
        f.write(output)
        tmp_path = Path(f.name)
    
    tmp_path.rename(target)
    print(f"Created {target}")
    return target
```

**Tests:**
- Header present with correct format
- Timestamp in ISO format
- Template path recorded
- Comments from template preserved in body
- File written to correct location
- Temp file cleaned up (renamed away)

---

### Phase 7: Integration and Full-Flow Tests (Medium, ~1.5 hours)

**Tasks:**
- Wire all components together in `configure()`
- End-to-end tests with `_cmd_add`
- Verify no regression in existing onboarding flow

**Implementation:**

```python
def configure(self, repo_path: Path, template_path: Path | None = None) -> Path | None:
    """
    Generate llmc.toml for repo.
    
    Returns:
        Path to generated config, or None if skipped/aborted.
    
    Raises:
        FileNotFoundError: Template not found
        ValueError: Invalid template TOML
        SystemExit: User aborted
    """
    # 1. Resolve and load template
    resolved_template = self._find_template(template_path)
    doc = self._load_template(resolved_template)
    
    # 2. Handle existing file
    target = repo_path / "llmc.toml"
    action = self._handle_existing(target)
    
    if action == "skip":
        return None
    elif action == "abort":
        raise SystemExit(1)
    
    # 3. Collect options
    options = self._collect_options(repo_path, doc)
    
    # 4. Transform
    self._transform(doc, options)
    
    # 5. Write
    return self._write_config(doc, repo_path, resolved_template)
```

**Tests:**
- New repo without existing config: full flow succeeds
- Repo with existing config (interactive keep): returns None
- Repo with existing config (interactive replace): backup + new file
- Non-interactive with existing: skips, returns None
- Generated config has correct paths and overrides
- Registry and workspace unaffected by configurator errors

---

## 8. Security Considerations

- `allowed_roots` and `workspace.root` are set to the intended repo path only
- User-supplied exclude patterns only narrow indexing scope
- No expansion of filesystem access beyond repo root
- Template paths are resolved but not executed

---

## 9. Compatibility

- Does not change behavior for existing repos (only runs during `add`)
- Existing `llmc.toml` files are never modified without explicit user consent
- LLMC's root `llmc.toml` remains the canonical template and documentation

---

## Appendix Z: Speculative Enhancements (Out of Scope)

The following ideas are captured for future consideration but are explicitly not part of v1:

1. **Template Library:** Named profiles (`--profile python-ml`, `--profile typescript-web`) for different project types.

2. **Automatic Merging:** Smarter handling of existing configs when templates change, guided by header metadata.

3. **Validate Command:** `llmc-rag-repo validate` to check endpoint reachability and model availability.

4. **Diff Command:** `llmc-rag-repo diff` to show differences between repo config and current template.

5. **Dynamic Suggestions:** Analyze repo contents to suggest exclude patterns (detect `node_modules`, `venv`, etc.).

6. **Remote Templates:** Fetch templates from central server for pip-installed LLMC.

7. **Version Metadata:** Embed LLMC version or schema version for migration support.

8. **Post-Generation Hooks:** Run user-specified scripts after config generation.

---

*End of document*
