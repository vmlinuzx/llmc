SDD – Phase 1 Red-Risk Hardening (Implementation)  

Status: Ready for implementation  
Owner: Dave / LLMC Core  
Related Docs:  

SDD_Phase1_Red_Risk_Hardening.md (design-level)  

TESTING_GAP_ANALYSIS_NOV18.md  

Goal: Implement a focused, non-half-assed hardening pass over LLMC’s RAG stack for:  

Path traversal safety  

DB / SQL safety  

Subprocess safety  

Config & registry validation  

This is not a generic security rewrite; it’s a surgical pass to remove the most obvious foot-guns and codify their behavior in tests.  

  

1. Scope & Non-Scope  

1.1 In Scope  

Path traversal safety  

Introduce a single, reusable helper for “safe subpath under a root”.  

Wire it into:  

Workspace planning (tools/rag_repo/workspace.py).  

Repo registry (tools/rag_repo/registry.py).  

Daemon registry (tools/rag_daemon/registry.py) when constraints are configured.  

DB / SQL safety  

Audit tools/rag/database.py and related modules for dynamic SQL.  

Ensure user/config data is always passed as parameters.  

Add a focused regression test that tries to inject via files.path/files.lang and verifies files table stays intact.  

Subprocess safety  

Confirm all subprocess.run / check_output calls using user-ish data:  

Use list arguments.  

Do not use shell=True.  

Add tests that enforce this pattern for key code paths.  

Config & registry validation  

Add minimal validation for ToolConfig and registry entries.  

Reject obviously broken configs/paths early with clear messages.  

Test refactor for relevant parts of test_error_handling_comprehensive.py  

Move “real” guarantees into focused test modules.  

Leave test_error_handling_comprehensive.py as a thin wrapper or spec, not the only place where behavior is enforced.  

1.2 Out of Scope (Phase 1)  

Full security review of every module.  

Encryption / secrets management / multi-tenant sandboxing.  

Performance tuning, routing logic changes, or daemon scheduling changes.  

Large API surface changes (CLI flags, MCP contracts, etc.).  

  

2. High-Level Design Summary  

Phase 1 is implemented as small, targeted code changes plus focused tests:  

A single path helper (safe_subpath) becomes the canonical way to accept a user-specified path under a root.  

DB layer is confirmed to be parameterized; an injection test codifies this.  

Subprocess calls are locked into safe patterns and regression-tested.  

Config / registry gain basic schema + path validation.  

The giant “comprehensive” test file is decomposed so that important guarantees live in smaller, direct tests.  

  

3. Detailed Implementation Plan  

3.1 Path Traversal Safety  

3.1.1 New helper: PathTraversalError + safe_subpath  

File: tools/rag_repo/utils.py  

Changes:  

Add type alias (optional) and exception:  

from pathlib import Path  
from typing import Union  
  
PathLike = Union[str, Path]  
  
  
class PathTraversalError(ValueError):  
   """Raised when a user-controlled path escapes an allowed root."""  
  

Add helper:  

def safe_subpath(base: Path, user_path: PathLike) -> Path:  
   """  
   Resolve a user-controlled path under a fixed base directory.  
  
   - Expands '~' when user_path is a string.  
   - Resolves symlinks.  
   - Ensures the resulting path is within base.  
   - Raises PathTraversalError if the path escapes base.  
   """  
   base_resolved = base.expanduser().resolve()  
   user = Path(user_path).expanduser()  
  
   if user.is_absolute():  
       candidate = user.resolve()  
   else:  
       candidate = (base_resolved / user).resolve()  
  
   try:  
       candidate.relative_to(base_resolved)  
   except ValueError:  
       raise PathTraversalError(f"Path traversal blocked: {user_path!r}")  
  
   return candidate  
  

Keep canonical_repo_path untouched except maybe using .expanduser().resolve() if not already.  

3.1.2 Workspace planning  

File: tools/rag_repo/workspace.py  

Current behavior (conceptual):  

plan_workspace(repo_root, tool_config, inspection):  

Resolves repo_root.  

If a workspace already exists, uses that.  

Otherwise, uses tool_config.default_workspace_folder_name appended to the repo root.  

New behavior:  

from .utils import canonical_repo_path, safe_subpath, PathTraversalError  
  
def plan_workspace(repo_root: Path, tool_config: ToolConfig, inspection: RepoInspection) -> WorkspacePlan:  
   base = canonical_repo_path(repo_root)  
  
   if inspection.workspace_path is not None:  
       workspace_root = safe_subpath(base, inspection.workspace_path)  
   else:  
       workspace_root = safe_subpath(base, tool_config.default_workspace_folder_name)  
  
   # derive config_dir, indexes_dir, logs_dir, tmp_dir from workspace_root as today  
  

CLI behavior:  

Wherever plan_workspace() is called in the llmc-rag-repo CLI:  

Catch PathTraversalError:  

Log a clear error message.  

Exit non-zero.  

Example:  

from tools.rag_repo.utils import PathTraversalError  
  
try:  
   plan = plan_workspace(...)  
except PathTraversalError as exc:  
   logger.error("Invalid workspace path: %s", exc)  
   sys.exit(1)  
  

3.1.3 Repo registry  

File: tools/rag_repo/registry.py  

Current (simplified):  

repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))  
rag_workspace_path = canonical_repo_path(Path(os.path.expanduser(data["rag_workspace_path"])))  
  

New:  

from .utils import canonical_repo_path, safe_subpath, PathTraversalError  
  
repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))  
  
rag_workspace_raw = data.get("rag_workspace_path")  
if rag_workspace_raw is not None:  
   try:  
       rag_workspace_path = safe_subpath(repo_path, rag_workspace_raw)  
   except PathTraversalError as exc:  
       logger.warning("Skipping registry entry for %s: invalid workspace path: %s", repo_path, exc)  
       return None  # or skip this record based on existing patterns  
else:  
   # Fallback: default under repo root  
   rag_workspace_path = safe_subpath(repo_path, DEFAULT_WORKSPACE_FOLDER_NAME)  
  

Behavior:  

Entries whose workspace points outside the repo root are ignored, not silently accepted.  

3.1.4 Daemon registry constraints  

Files:  

tools/rag_daemon/config.py (or equivalent)  

tools/rag_daemon/registry.py  

Config extension:  

from pathlib import Path  
from dataclasses import dataclass  
from typing import Optional  
  
@dataclass  
class DaemonConfig:  
  

You said:  

Just output to a .md file for me to download please, the web is broken garbage.  

ChatGPT said:  

Thought for 27s  

Alright, tools are clearly having a meltdown, so I’ll do this the caveman way: here’s the full .md content inline. You can copy-paste it into a file named:  

SDD_Phase1_Red_Risk_Hardening_Implementation.md  

and you’re good.  

  

# SDD – Phase 1 Red-Risk Hardening (Implementation)  
  
**Status:** Ready for implementation    
**Owner:** Dave / LLMC Core    
**Related Docs:**    
- `SDD_Phase1_Red_Risk_Hardening.md` (design-level)    
- `TESTING_GAP_ANALYSIS_NOV18.md`    
  
**Goal:** Implement a focused, non-half-assed hardening pass over LLMC’s RAG stack for:  
  
- Path traversal safety    
- DB / SQL safety    
- Subprocess safety    
- Config & registry validation    
  
This is **not** a generic security rewrite; it’s a surgical pass to remove the most obvious foot-guns and codify their behavior in tests.  
  
---  
  
## 1. Scope & Non-Scope  
  
### 1.1 In Scope  
  
1. **Path traversal safety**  
  - Introduce a reusable helper for “safe subpath under a root”.  
  - Wire it into:  
    - Workspace planning (`tools/rag_repo/workspace.py`).  
    - Repo registry (`tools/rag_repo/registry.py`).  
    - Daemon registry (`tools/rag_daemon/registry.py`) when constraints are configured.  
  
2. **DB / SQL safety**  
  - Audit `tools/rag/database.py` and related modules for dynamic SQL.  
  - Ensure user/config data is always passed as parameters.  
  - Add a focused regression test that attempts injection via `files.path` / `files.lang` and verifies the `files` table remains intact.  
  
3. **Subprocess safety**  
  - Confirm all `subprocess.run` / `check_output` calls with user-ish input:  
    - Use list arguments.  
    - Do **not** use `shell=True`.  
  - Add tests that enforce this pattern for key code paths.  
  
4. **Config & registry validation**  
  - Add minimal validation for `ToolConfig` and registry entries.  
  - Reject obviously broken configs/paths early with clear messages.  
  
5. **Test refactor for relevant parts of `test_error_handling_comprehensive.py`**  
  - Move “real” guarantees into focused test modules.  
  - Leave `test_error_handling_comprehensive.py` as a thin wrapper/spec, not the only place where behavior is enforced.  
  
### 1.2 Out of Scope (Phase 1)  
  
- Full security review of every module.    
- Encryption / secrets management / multi-tenant sandboxing.    
- Performance tuning, routing logic changes, or daemon scheduling changes.    
- Large public API changes (CLI flags, MCP contracts, etc.).    
  
---  
  
## 2. High-Level Implementation Summary  
  
Phase 1 is implemented as **small, targeted code changes** plus **focused tests**:  
  
- A **single path helper** (`safe_subpath`) becomes the canonical way to accept a user-specified path under a root.    
- **DB layer** is confirmed to be parameterized; an injection test codifies this.    
- **Subprocess calls** are locked into safe patterns and regression-tested.    
- **Config / registry** gain basic schema + path validation.    
- The giant “comprehensive” test file is decomposed so important guarantees live in smaller, direct tests.  
  
Each of these pieces is implemented in a way that keeps diffs reviewable and minimizes behavioral surprises for current users.  
  
---  
  
## 3. Detailed Implementation Plan  
  
### 3.1 Path Traversal Safety  
  
#### 3.1.1 New helper: `PathTraversalError` + `safe_subpath`  
  
**File:** `tools/rag_repo/utils.py`  
  
**Additions:**  
  
```python  
from pathlib import Path  
from typing import Union  
  
PathLike = Union[str, Path]  
  
  
class PathTraversalError(ValueError):  
   """Raised when a user-controlled path escapes an allowed root."""  
  
  
def safe_subpath(base: Path, user_path: PathLike) -> Path:  
   """  
   Resolve a user-controlled path under a fixed base directory.  
  
   - Expands '~' when user_path is a string.  
   - Resolves symlinks.  
   - Ensures the resulting path is within base.  
   - Raises PathTraversalError if the path escapes base.  
   """  
   base_resolved = base.expanduser().resolve()  
   user = Path(user_path).expanduser()  
  
   if user.is_absolute():  
       candidate = user.resolve()  
   else:  
       candidate = (base_resolved / user).resolve()  
  
   try:  
       candidate.relative_to(base_resolved)  
   except ValueError:  
       raise PathTraversalError(f"Path traversal blocked: {user_path!r}")  
  
   return candidate  
  

Notes:  

canonical_repo_path may continue to exist as a convenience; it should internally use .expanduser().resolve() if it doesn’t already.  

safe_subpath is explicitly for user-controlled paths relative to a base; use it whenever you accept workspace paths, repo paths under a root, or similar.  

New tests: tests/test_path_safety.py  

from pathlib import Path  
import pytest  
  
from tools.rag_repo.utils import safe_subpath, PathTraversalError  
  
  
def test_safe_subpath_allows_normal_relative(tmp_path):  
   base = tmp_path  
   p = safe_subpath(base, "src/main.py")  
   assert p == base / "src/main.py"  
   assert p.is_absolute()  
  
  
def test_safe_subpath_normalizes_dots(tmp_path):  
   base = tmp_path  
   p = safe_subpath(base, "src/../src/main.py")  
   assert p == base / "src/main.py"  
  
  
def test_safe_subpath_allows_absolute_inside(tmp_path):  
   base = tmp_path  
   target = (base / "a/b/c.txt")  
   target.parent.mkdir(parents=True)  
   target.touch()  
   p = safe_subpath(base, target)  
   assert p == target.resolve()  
  
  
def test_safe_subpath_blocks_parent_escape(tmp_path):  
   base = tmp_path / "root"  
   base.mkdir()  
   with pytest.raises(PathTraversalError):  
       safe_subpath(base, "../../etc/passwd")  
  

(An additional symlink-outside test can be added if the platform behaves consistently with symlinks.)  

  

3.1.2 Workspace planning  

File: tools/rag_repo/workspace.py  

Before (conceptual):  

plan_workspace(repo_root, tool_config, inspection):  

Resolves repo_root using canonical_repo_path.  

If inspection.workspace_path exists, trusts it.  

Otherwise uses tool_config.default_workspace_folder_name appended to repo root.  

After:  

from pathlib import Path  
  
from .utils import canonical_repo_path, safe_subpath, PathTraversalError  
  
  
def plan_workspace(repo_root: Path, tool_config: ToolConfig, inspection: RepoInspection) -> WorkspacePlan:  
   base = canonical_repo_path(repo_root)  
  
   if inspection.workspace_path is not None:  
       workspace_root = safe_subpath(base, inspection.workspace_path)  
   else:  
       workspace_root = safe_subpath(base, tool_config.default_workspace_folder_name)  
  
   # existing logic: derive config_dir, indexes_dir, logs_dir, tmp_dir from workspace_root  
   ...  
  

CLI behavior:  

In the llmc-rag-repo CLI, where plan_workspace() is called:  

from tools.rag_repo.utils import PathTraversalError  
  
try:  
   workspace_plan = plan_workspace(...)  
except PathTraversalError as exc:  
   logger.error("Invalid workspace path: %s", exc)  
   sys.exit(1)  
  

Tests: tests/test_rag_repo_workspace.py  

Normal case: workspace under repo root → accepted.  

Malicious case: workspace path pointing outside ("../outside", "/etc") → PathTraversalError raised, not silently accepted.  

  

3.1.3 Repo registry  

File: tools/rag_repo/registry.py  

Before (simplified):  

repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))  
rag_workspace_path = canonical_repo_path(Path(os.path.expanduser(data["rag_workspace_path"])))  
  

After:  

from pathlib import Path  
import os  
import logging  
  
from .utils import canonical_repo_path, safe_subpath, PathTraversalError  
  
logger = logging.getLogger(__name__)  
  
  
def _load_registry_entry(data: dict) -> RegistryEntry | None:  
   repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))  
  
   raw_workspace = data.get("rag_workspace_path")  
   if raw_workspace is not None:  
       try:  
           rag_workspace_path = safe_subpath(repo_path, raw_workspace)  
       except PathTraversalError as exc:  
           logger.warning(  
               "Skipping registry entry for %s: invalid workspace path: %s",  
               repo_path,  
               exc,  
           )  
           return None  
   else:  
       # Fallback to default under repo root  
       rag_workspace_path = safe_subpath(repo_path, DEFAULT_WORKSPACE_FOLDER_NAME)  
  
   # construct and return RegistryEntry using repo_path, rag_workspace_path, etc.  
   ...  
  

Behavior:  

Registry entries whose workspace is outside the repo root are explicitly skipped and logged.  

Good entries behave as before but are now validated.  

Tests: tests/test_rag_repo_registry.py  

Valid entry: repo path and workspace path under repo → entry returned.  

Invalid entry: workspace with ../.. segments → returns None or is omitted from load_all(), with a warning logged.  

  

3.1.4 Daemon registry constraints  

Files:  

tools/rag_daemon/config.py (or equivalent)  

tools/rag_daemon/registry.py  

Config changes:  

from pathlib import Path  
from dataclasses import dataclass  
from typing import Optional  
  
@dataclass  
class DaemonConfig:  
   # existing fields...  
   repos_root: Optional[Path] = None  
   workspaces_root: Optional[Path] = None  
  

Registry loading changes:  

In RegistryClient.load() or equivalent, after raw paths are extracted:  

from pathlib import Path  
from tools.rag_repo.utils import safe_subpath, PathTraversalError  
  
def _normalize_paths(config: DaemonConfig, raw_repo_path: str, raw_workspace_path: str | None) -> tuple[Path, Path | None]:  
   if config.repos_root is not None:  
       repo_path = safe_subpath(config.repos_root, raw_repo_path)  
   else:  
       repo_path = Path(raw_repo_path).expanduser().resolve()  
  
   workspace_path: Path | None  
   if raw_workspace_path is not None:  
       if config.workspaces_root is not None:  
           workspace_path = safe_subpath(config.workspaces_root, raw_workspace_path)  
       else:  
           workspace_path = Path(raw_workspace_path).expanduser().resolve()  
   else:  
       workspace_path = None  
  
   return repo_path, workspace_path  
  

Then ensure _is_safe_path checks still run on the resolved paths to prevent repositories under /etc, /proc, /sys, /dev, /root.  

Tests: tests/test_rag_daemon_registry.py  

When repos_root is set:  

Repo inside repos_root → accepted.  

Repo outside repos_root → PathTraversalError or explicit rejection.  

Similarly for workspaces_root.  

  

3.2 DB & SQL Safety  

Files:  

tools/rag/database.py  

tests/test_db_security.py (new)  

tests/test_error_handling_comprehensive.py (cleanup)  

3.2.1 Audit & guardrails  

Implementation steps:  

Search in tools/rag/database.py and any adjacent DB helper modules for:  

f"SELECT  

f"INSERT  

f"UPDATE  

f"DELETE  

For each dynamic SQL site:  

If dynamic parts are internal constants (table/column names, fixed placeholder strings), keep them and add:  

# OK: table/column names are internal, not user-controlled  
  

If any interpolated value may contain user/config text, refactor to parameters, e.g.:  

# BAD  
sql = f"SELECT * FROM files WHERE path = '{path}'"  
conn.execute(sql)  
  
# GOOD  
sql = "SELECT * FROM files WHERE path = ?"  
conn.execute(sql, (path,))  
  

This pass should be small but explicit, making future reviews easier.  

3.2.2 Injection regression test  

New file: tests/test_db_security.py  

from pathlib import Path  
  
from tools.rag.database import Database, FileRecord  
  
  
def test_sql_injection_attempt_does_not_drop_files_table(tmp_path):  
   db_path = tmp_path / "index.db"  
   db = Database(db_path)  
  
   malicious_path = "test.py'; DROP TABLE files; --"  
   malicious_lang = "python'; DROP TABLE files; --"  
  
   rec = FileRecord(  
       path=malicious_path,  
       lang=malicious_lang,  
       # fill in required fields with minimal valid values  
   )  
   db.upsert_file(rec)  
  
   cursor = db.conn.execute("SELECT COUNT(*) FROM files")  
   (count,) = cursor.fetchone()  
   assert count >= 1  
  

Cleanup:  

Remove or simplify the equivalent logic in tests/test_error_handling_comprehensive.py to avoid duplicated behavior.  

That file may retain a single high-level test that simply asserts “injection does not break DB”, delegating all specifics to test_db_security.py.  

  

3.3 Subprocess Safety  

Files:  

tools/rag/utils.py  

tools/rag_daemon/workers.py  

tools/rag_nav/gateway.py  

scripts/qwen_enrich_batch.py  

tools/dev/quality_baseline.py  

tests/test_subprocess_safety.py (new)  

3.3.1 Enforcement  

Implementation:  

Manual/grep audit for all subprocess.run and subprocess.check_output usages.  

Ensure all of them:  

Use argument lists (["git", "status"]), not shell-joined strings.  

Do not use shell=True where user or config input is involved (ideally, not at all).  

If any shell=True remains and is not strictly internal/safe, replace with list-based invocation.  

3.3.2 Regression tests  

New file: tests/test_subprocess_safety.py  

Example structure:  

import subprocess  
  
import pytest  
  
import tools.rag.utils as rag_utils  
from tools.rag_daemon import workers  
from tools.rag_nav import gateway  
  
  
def _assert_no_shell_and_list_args(calls):  
   for args, kwargs in calls:  
       cmd = args[0]  
       assert isinstance(cmd, (list, tuple)), "Expected subprocess args to be a list/tuple"  
       assert not kwargs.get("shell"), "shell=True must not be used for these calls"  
  
  
def test_git_helpers_use_safe_subprocess(monkeypatch, tmp_path):  
   calls = []  
  
   def fake_run(*args, **kwargs):  
       calls.append((args, kwargs))  
  
       class Result:  
           returncode = 0  
           stdout = "abc123\n"  
           stderr = ""  
  
       return Result()  
  
   monkeypatch.setattr(subprocess, "run", fake_run)  
  
   # Adjust to match actual helper names  
   _ = rag_utils.git_commit_sha(tmp_path)  
  
   _assert_no_shell_and_list_args(calls)  
  

Additional tests can be added for:  

Daemon worker runner (_invoke_runner or equivalent).  

Any CLI helpers that shell out to git or external tools.  

If some helpers use subprocess.check_output, they should be similarly wrapped/monkeypatched and checked.  

  

3.4 Config & Registry Validation  

Files:  

tools/rag_repo/config.py  

tools/rag_repo/registry.py (already touched for paths)  

tests/test_rag_repo_config.py (new)  

3.4.1 Tool config validation  

In tools/rag_repo/config.py:  

Add:  

from dataclasses import dataclass  
from typing import List  
  
  
@dataclass  
class ConfigValidationIssue:  
   field: str  
   message: str  
   severity: str  # "error" | "warning"  
  

Add validator:  

def validate_tool_config(cfg: ToolConfig) -> list[ConfigValidationIssue]:  
   issues: list[ConfigValidationIssue] = []  
  
   if not cfg.registry_path:  
       issues.append(ConfigValidationIssue(  
           field="registry_path",  
           message="Registry path is not set",  
           severity="error",  
       ))  
   elif not cfg.registry_path.parent.exists():  
       issues.append(ConfigValidationIssue(  
           field="registry_path",  
           message="Parent directory of registry_path does not exist",  
           severity="warning",  
       ))  
  
   # Additional small checks can be added here later.  
  
   return issues  
  

CLI integration:  

Where ToolConfig is loaded in the repo CLI:  

cfg = load_tool_config(config_path)  
issues = validate_tool_config(cfg)  
  
errors = [i for i in issues if i.severity == "error"]  
for issue in issues:  
   log_fn = logger.error if issue.severity == "error" else logger.warning  
   log_fn("Config issue (%s): %s - %s", issue.severity, issue.field, issue.message)  
  
if errors:  
   sys.exit(1)  
  

Tests: tests/test_rag_repo_config.py  

Test that missing registry path yields an error issue.  

Test that nonexistent parent directory yields a warning issue.  

Further registry-specific structure validation (beyond paths) can be incrementally added in later phases if needed.  

  

3.5 Test Suite Changes for test_error_handling_comprehensive.py  

File: tests/test_error_handling_comprehensive.py  

This file should be trimmed so that:  

Path traversal tests:  

Either call the real safe_subpath helper and assert malicious inputs fail, or  

Are removed in favor of the dedicated test_path_safety.py.  

SQL injection tests:  

Delegate to test_db_security.py; the comprehensive file might keep only a single high-level smoke test, if any.  

Any tests that do not call actual LLMC code and just do try: assert True / “demo the vulnerability” should either:  

Be deleted, or  

Be marked @pytest.mark.xfail(strict=True, reason="spec-only, behavior enforced elsewhere") until a proper implementation exists.  

Goal: the comprehensive file is supplementary, not the sole enforcer of critical guarantees.  

  

4. Implementation Order / Suggested Commits  

A sane sequence that keeps diffs small and understandable:  

Commit 1 – Path helpers + tests  

Add PathTraversalError + safe_subpath to tools/rag_repo/utils.py.  

Add tests/test_path_safety.py and get it green.  

Commit 2 – Workspace & repo registry wiring  

Update plan_workspace() to use safe_subpath.  

Update RegistryAdapter loading to validate workspaces with safe_subpath.  

Extend tests/test_rag_repo_workspace.py and tests/test_rag_repo_registry.py accordingly.  

Commit 3 – Daemon registry constraints  

Extend DaemonConfig with repos_root / workspaces_root.  

Wire _normalize_paths / RegistryClient.load() to use safe_subpath when constraints are present.  

Add or extend tests/test_rag_daemon_registry.py.  

Commit 4 – DB security test + audit  

Add tests/test_db_security.py.  

Audit tools/rag/database.py for parameterization and add comments.  

Clean up any overlapping logic in test_error_handling_comprehensive.py.  

Commit 5 – Subprocess safety tests  

Add tests/test_subprocess_safety.py.  

Fix any discovered shell=True or string-based command issues.  

Commit 6 – Config validation  

Add ConfigValidationIssue + validate_tool_config() to tools/rag_repo/config.py.  

Wire into CLI, add tests/test_rag_repo_config.py.  

Commit 7 – Comprehensive test cleanup  

Trim / xfail redundant or spec-only tests in test_error_handling_comprehensive.py now that behavior is enforced in dedicated modules.  

After these commits, Phase 1 is “not half-assed”: the core red-risk vectors (paths, SQL, subprocess, config) are guarded by code and pinned by tests.  

 