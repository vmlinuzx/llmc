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

1.1 In Scope  Skip to content
Chat history

You said:
llmc.zip
Zip Archive
TESTING_GAP_ANALYSIS_NOV18.md
File
test_error_handling_comprehensive.py
Python
Roswaal delivered this with a sneer.
ChatGPT said:

Thought for 1m 32s
Yeah, he did. That’s a “my lord, your castle is impressive but also on fire” kind of report.

Let me translate what Roswaal actually just told you in human terms.

1. What the gap report really says
From TESTING_GAP_ANALYSIS_NOV18.md:

Test infra is solid

769 tests collected, everything discoverable.

RAG suite: 16/17 passing (94.1%). 

But your code quality is actively decaying

406 Ruff violations, up from 312 last week (+30% trend the wrong way).

14 bare except: (E722) and 31 undefined names (F821). 

Missing / weak coverage in serious places

Service layer test failing because the server script isn’t even wired.

Path traversal & input validation around registry and repo paths not tested / not fixed. 

Limited performance, concurrency, and long-running daemon tests.

TL;DR:
You’ve got a real test spine, but the skeleton is wearing a lint-covered bathrobe and carrying a chainsaw labeled “bare except”.

2. What this new giant error-handling test file is (and isn’t)
test_error_handling_comprehensive.py is ambitious as hell:

It covers all the right domains in concept:

DB corruption, permissions, disk full, concurrent access, migrations, orphaned rows.

Network failures: timeouts, 429, 401, 500.

Filesystem insanity: symlink loops, FIFOs, very long paths.

Config & registry failures: malformed YAML, missing fields, invalid types/paths.

Security: SQL injection prevention, path traversal, subprocess misuse, git command injection, unicode weirdness.

Concurrency, resource exhaustion, data integrity, recovery. 

That part is excellent thinking. It’s basically a safety spec in code form.

But there are some hard truths:

2.1 A lot of tests don’t actually exercise your code
Example pattern (there are many like this):

@patch("tools.rag.enrichment.requests.post")
def test_enrichment_handles_connection_timeout(self, mock_post):
    from tools.rag.enrichment import enrich_spans
    mock_post.side_effect = Exception("Connection timeout")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # This would normally make a network call
            # With timeout, it should raise or handle gracefully
            assert True
        except Exception as e:
            assert e is not None
enrich_spans is imported but never called.

The test always passes, regardless of what your code does. 

This pattern repeats all over: “try: assert True / except: assert e is not None” without touching real logic.

Net effect:
👉 This file is more like a narrative design doc than a genuine failing test suite.

2.2 One test literally asserts that a vulnerability exists
test_handles_path_traversal explicitly documents that Path.resolve() doesn’t prevent traversal and then asserts that paths escape the repo root as a “vulnerability found”. 

That’s great as a security finding, but:

As a test, it currently says:
“This exploit works ✅”

Once you fix path validation, this test should flip to:
“This exploit no longer works ✅”.

Right now, it’s a “known bug detector”, not a guardrail.

2.3 Some tests are really “stdlib demos”
Examples:

Opening 1000 files to maybe hit “too many open files”.

Looping for i in range(10**10) and bailing after if i > 1000000.

Allocating big lists in a loop for “memory pressure.” 

These don’t verify how LLMC behaves, they just poke system limits.

Good for thinking, not for day-to-day CI.

3. How I’d turn this into something actually useful
Let’s treat what Roswaal gave you as a draft spec and carve it into something that earns its CPU time.

Step 1 – Split “spec tests” from “real tests”
Make two kinds of files:

Real, enforceable tests (CI must stay green)

Live in e.g. tests/test_error_handling_db.py, tests/test_error_handling_registry.py, etc.

Each test:

Calls actual code.

Makes clear, strict assertions.

Fails when behaviour regresses.

Exploratory / security-finding tests

Either:

Mark as xfail(strict=True, reason="known vuln: path traversal"), or

Move to tests/spec/ or tests/manual/ to run on-demand.

Document intended future behaviour so you know what to flip when fixed.

Right now test_error_handling_comprehensive.py is doing both at once and pleasing nobody.

Step 2 – Turn the big security findings into P0 code changes
From the gap report + this file, these are your true P0s:

P0.1 Path traversal hardening
Use the exact safe pattern already sketched in the test:

from pathlib import Path

def safe_resolve(user_path: str, base: Path) -> Path:
    resolved = (base / user_path).resolve()
    base_resolved = base.resolve()

    if not str(resolved).startswith(str(base_resolved)):
        raise ValueError(f"Path traversal blocked: {user_path}")

    return resolved
Put this in a shared utility, e.g. tools/rag/utils/paths.py.

Use it anywhere you currently do Path(user_input).resolve() or equivalent in:

RegistryClient (registry paths, workspace paths).

Any function that walks repo roots or workspaces based on config / user input.

Then flip test_safe_path_validation_example to assert your real helper is used / behaves correctly (right now it’s just a demo). 

P0.2 Subprocess safety
Your tests already bake in the correct subprocess usage pattern (list args, shell=False). 

Audit tools/rag/runner.py and any other subprocess call sites.

Enforce a hard rule:

No shell=True with user-controlled input.

No string commands where user input is interpolated.

You already have iter_repo_files using ["git", "ls-files", ...] which is good; the test just needs to actually assert assumptions (e.g., no shell=True flag).

P0.3 SQL injection / parameterization
test_handles_injection_attempts is actually pretty solid:
It inserts a malicious path and lang and then asserts:

The data is treated as data, not executable SQL.

The files table still exists. 

Action items:

Ensure all DB writes use parameterized queries (no f-strings with user data).

Maybe add a helper in Database to whitelist all query patterns that can accept user text.

This test is close to being real protection; it just needs to be wired as a normal part of your DB test suite and slightly tightened.

Step 3 – Fix the test hygiene that’s actively annoying pytest
From the gap report:

TestResult and TestRunner dataclasses in “comprehensive” tests clash with pytest’s “collect test classes” heuristics. 

Do this:

Rename them to RagTestResult, RagTestRunner, or even ResultSummary, RunnerSpec.

Or mark them with @pytest.mark.no_collect / move them out of tests/ if they’re helpers.

Tiny change, big reduction in pytest spam.

Step 4 – Make this file actually hit your code
Concrete upgrades to test_error_handling_comprehensive.py:

DB tests

Use public methods on Database instead of raw db.conn.execute where possible.

For corrupted DB, disk full, permission denied:

Call something like db.list_files() or db.upsert_file(...) and assert:

It raises a specific exception; or

It returns a documented error state.

Network tests (enrich_spans)

Right now, tests mock requests.post then… don’t call enrich_spans.

Fix them to:

Call enrich_spans(...) with a small fake span set.

Assert that on:

timeout → you get a retriable error / logged error / specific exception.

429 → backoff / retry / “rate limited” result.

401 / 500 → clear, typed error or graceful degradation.

Config / registry tests

For malformed YAML, missing fields, invalid paths:

Assert RegistryClient.load() returns a known shape (empty dict, or warnings) rather than just “not crashing”. 

Swap “try/except assert True” for precise expectations

Wherever you see:

try:
    assert True
except Exception as e:
    assert e is not None
Replace with something like:

with pytest.raises(ExpectedErrorType):
    ...call_function_that_should_fail(...)
or

result = call_function(...)
assert result.status == "ERROR"
assert "rate limit" in result.message
4. Priority stack I’d follow from here
Given your constraints (cheap, lazy, ADHD — your words 😄), here’s the ROI-first order:

P0 security + correctness

Implement safe_resolve and wire it into all path handling surfaces.

Confirm DB uses parameterized queries everywhere.

Audit subprocess usage; kill any shell=True with user input.

Tighten or mark as xfail the path traversal & injection tests so they encode desired future behaviour.

P0 quality debt

Run Ruff with a narrow scope:

ruff check tools/ scripts/ tests/ --select E722,F821
Fix:

All bare except: to specific exception types.

All undefined names (imports / typos / dead code). 

Test cleanup

Split test_error_handling_comprehensive.py into:

Enforced tests that call real code.

Spec/xfail tests for known issues.

Rename helper classes to avoid pytest confusion.

Service layer

Either:

Create a thin, testable server entrypoint to satisfy service_startup, or

Mark that test xfail with a clear reason until the service is genuinely wired.

5. How to use this going forward
If you treat what Roswaal gave you as:

TESTING_GAP_ANALYSIS_NOV18.md → your test strategy doc, and

test_error_handling_comprehensive.py → your error-handling + security spec,

then the next concrete move is:

Start pulling scenarios out of that spec and turning them into sharp, minimal tests that fail on real regressions.

You don’t need to do all of it at once. Pick one vertical (e.g., “path & registry safety”) and:

Implement safe_resolve + registry hardening.

Fix / tighten the two or three tests that touch that logic.

Move on.

When you’re ready to weaponize one of these slices (e.g. “P0 – path & registry hardening”), tell me which slice you’re working on and I’ll help you convert that part of the spec into a tight patch + focused test module instead of a giant omnibus.

You said:
Ok, please build me a solid set of nested roadmap entries to get us to a grade of "good enough for gubmint work"
ChatGPT said:

Thought for 1m 3s
Alright, here’s your “passes federal inspection without bribery” roadmap.

I’ve put the full nested version with checkboxes into a markdown file you can download here:

Download the LLMC Quality Roadmap (.md)

Here’s the high-level structure so you can eyeball it in chat:

0. Definition of “Good Enough for Government Work”
No obvious foot-guns on:

Path traversal

SQL injection

Subprocess misuse

Core surfaces return a structured error envelope (e.g. RagToolMeta-style).

P0 surfaces (security, DB, registry, router/daemon) all have direct tests.

bare except: and undefined-name nonsense cleaned up.

CI: one command, clean run, no flakiness on a fresh clone.

Basic runbooks exist for “service won’t start / index is corrupted / RAG looks wrong”.

1. Phase 1 – Red-Risk Hardening (Security & Data Integrity)
1.1 Filesystem & path safety

Implement a shared safe_resolve(base, user_path) helper that:

Resolves + normalizes.

Enforces “must stay under base”.

Use it everywhere untrusted paths come in (registry, repo roots, workspaces).

Replace the current “path traversal vulnerability demo” tests with:

Real “this now fails safely” tests.

Or strict xfail until fixed.

1.2 Database & SQL safety

Audit all SQL sites; enforce parameterized queries for any user/config text.

Centralize DB writes in a small API surface.

Tests that try injection via:

Paths, filenames, langs, descriptions.

Assert:

Schema intact.

Malicious strings stored as data, not executed.

1.3 Subprocess & command exec safety

Inventory all subprocess usage.

Rules:

No shell=True with untrusted input.

Always pass arg lists, not shell strings.

Tests:

Mock subprocess, assert shell=False and list args in the real code paths.

1.4 Config & registry validation

Define schemas for config/registry files (required keys, types, enums).

Implement validate_config / validate_registry_entry.

Tests for missing keys, wrong types, invalid paths → predictable exceptions / error responses.

2. Phase 2 – Structured Error Handling & Recovery
2.1 Standard error envelope

Finalize meta schema (status, error_code, message, source, freshness_state).

Apply to:

RAG tools (search / where-used / lineage).

CLI/daemon APIs.

Tests for forced failures:

Assert status="ERROR", stable error_code, useful message.

2.2 Network & LLM provider failures

Map provider failures to internal codes:

Timeouts, connection errors, 429, 4xx auth, 5xx.

Implement retry/backoff for transient errors, fast-fail for bad requests.

Mock-based tests to verify retry logic and final structured errors.

2.3 DB corruption & migration

On DB open:

Integrity + schema-version checks.

On mismatch:

Attempt migration, otherwise return clear error with next steps.

Tests with corrupted/old/missing-schema DBs.

2.4 Daemon & workers

Job-level error containment:

One job fails ≠ whole daemon dies.

Tests:

Fake job that always throws → daemon survives, failure visible via status/logs.

3. Phase 3 – Test Suite Hygiene & Signal
3.1 Convert spec-tests into real tests

Triage test_error_handling_comprehensive.py:

Convert keepers into real tests that call LLMC code.

Mark “known bug / future behavior” with strict xfail.

Drop pure stdlib demos from CI.

Replace try: assert True patterns with:

pytest.raises(...) or

Assertions on results/envelopes.

3.2 Lint & style as a gate

Fix all:

bare except: (E722)

undefined names (F821)

Add a minimal Ruff gate in CI for those rules only.

Optionally expand lint rules later once the fires are out.

3.3 Smoke / regression tests

“Tiny repo” smoke tests:

index, search, where-used, plan on fixtures.

Assert:

Exit code 0.

No tracebacks.

Basic shape of output correct.

Tag any slow/perf checks appropriately.

4. Phase 4 – Observability & Ops
4.1 Logging & metrics

Standardize error logging fields:

Component, error code, message, context.

Tests:

Use caplog to assert logs for key failure paths.

4.2 Operator runbooks

Write short runbooks for:

Index corrupted/missing.

Service won’t start.

RAG results stale/wrong.

Each includes symptoms, log hints, diagnostics, and safe remediation steps.

4.3 Security/compliance checklist

Simple checklist for releases:

Path traversal protections tested.

DB/subprocess patterns safe.

Errors/logs do not leak secrets.

Run before major releases; keep in the repo.

5. Phase 5 – Stretch / Nice-to-Haves
Chaos-ish tests for indexing/daemon (kills, network flakiness).

Automated test-gap reports over time.

Optional dependency/security scanners wired into CI.

Suggested execution order (for Cheap, Lazy, ADHD Dave™)
Phase 1 – Path/DB/subprocess/config hardening (maximum risk reduction per line of code).

Phase 2 – Standard error envelopes + network/DB failure handling.

Phase 3 – Clean test suite + lint gate + smoke tests.

Phase 4 – Logs and runbooks, so Future You doesn’t hate Past You.

Phase 5 – Only if you’re feeling spicy.

If you want, next step we can zoom in on just Phase 1 and turn it into a concrete “patch + tests” to-do list for Beatrice/Roswaal to implement directly. 

You said:
Man.. this doesn't seem like fun.
ChatGPT said:

Thought for 29s
Yeah, no shit it doesn’t seem fun.
This is the broccoli part of the meal. Necessary, not sexy.

Let’s cheat.

Instead of “grand roadmap of righteousness,” let’s cut it down to “Government-Minimum Fast Track” — the actual stuff you need to not be ashamed if someone else runs LLMC in production.

1. The Real Minimum (do these and call it “good enough”)
If you only do this list, you’re in “good enough for gubmint work” territory:

A. Kill the obvious foot-guns
Implement safe_resolve and use it in 2 places

One helper: safe_resolve(base, user_path) that:

Normalizes + resolves.

Throws if the path escapes base.

Wire it into:

Registry/workspace path handling.

Repo root resolution from config.

Add 2–3 tests:

“Normal path works.”

“.. escapes → boom.”

“Sneaky symlink → boom.”

Quick DB injection sanity

Audit DB writes:

Any place you see f-string SQL with user/config text → parameterized query.

One dedicated test:

Insert malicious filenames/paths/langs,

Assert:

Data is stored as-is.

DB schema still exists / no crash.

Subprocess safety pass

Grep for subprocess usage.

Rules:

shell=True + user input → NO.

Prefer subprocess.run([...]) with arg lists.

One test that mocks subprocess.run and asserts it’s called with:

shell=False

list args, not a big string.

That’s security & integrity at “I’m not going to jail” level.

B. Make tests not lie to you
Triage test_error_handling_comprehensive.py

You don’t need to “fix it all”; you need to stop it from bullshitting you:

For tests that:

Don’t call your code

Or do try: assert True

→ Either:

Turn them into real tests that call actual functions, or

Mark them:

@pytest.mark.xfail(strict=True, reason="spec / known gap")
Anything that’s just “stdlib demo” or “I opened 1000 files for vibes”:

Move to tests/spec or delete.

Goal: after this, your test suite:

Only passes when reality is actually okay.

Fails when something real broke.

Doesn’t pretend to test things it doesn’t touch.

C. Stop the most embarrassing lint problems
One Ruff sweep, two rules only

Run:

ruff check . --select E722,F821 --fix
Then fix whatever’s left:

E722 – bare except:

Change to except Exception: or more specific.

F821 – undefined names

Add missing imports, delete dead references, fix typos.

That’s it. No full style crusade. Just “we don’t ship obvious broken crap.”

2. What that gets you
After those 5 moves:

Path traversal: guarded.

Obvious SQL injection: mitigated.

Subprocess: not trivially exploitable.

Tests: less lying, more signal.

Lint: no facepalm-level errors.

Is it perfect? Hell no.
Is it “good enough for government work” with a straight face? Yeah.

3. How to make this less un-fun for you
Knowing you:

Cheap → Make the computer do the grunt work.

Lazy → Fewer, bigger-leverage changes.

ADHD → Tiny, complete-able quests instead of endless slog.

So treat it like this:

Session 1 (90 minutes max)

Run Ruff, fix E722/F821.

Do the subprocess grep and clean any obvious shell=True stuff.

Session 2

Implement safe_resolve + 2–3 tests.

Wire it into registry + repo resolution.

Session 3

DB parameterization audit + one injection test.

Triage test_error_handling_comprehensive.py:

Convert/xfail/delete the worst offenders.

And if you want to outsource the misery to your agents, I can write you a tight “implement these 5 things, no scope creep” prompt for Beatrice/Roswaal so you just review diffs instead of grinding.

You don’t have to eat the whole roadmap.
We just need to flip the few switches that move you from “oh god no” to “fine, ship it.”

You said:
Let's start with Phase 1.  I want this shit to not look half assed.  
ChatGPT said:

Thought for 4m 20s

Thought for 2m 10s
Cool, Phase 1 is now actually real, not just vibes. 😈

I’ve dropped a full SDD for Phase 1 here (downloadable as requested):
➡️ /mnt/data/SDD_Phase1_Red_Risk_Hardening.md

That doc is the “this is not half-assed” version. Here’s the short, actionable view so you don’t have to scroll a novel in the chat.

Phase 1 – What We’re Actually Doing
1. Path Traversal Safety (the big one)
Core idea: introduce a single, real helper for “only operate under this root” and wire it where it matters.

New API (in tools/rag_repo/utils.py):

class PathTraversalError(ValueError):
    """Raised when a user-controlled path escapes an allowed root."""


def safe_subpath(base: Path, user_path: str | Path) -> Path:
    """
    Resolve a user-controlled path under a fixed base directory.

    - Expands '~' in user_path when string-like.
    - Resolves symlinks.
    - Ensures the resulting path is within base.
    - Raises PathTraversalError if the path escapes base.
    """
Implementation uses:

base_resolved = base.expanduser().resolve()

candidate = (base_resolved / user).resolve() (or user.resolve() if absolute)

candidate.relative_to(base_resolved) → if that explodes, raise PathTraversalError.

Where it gets used:

Workspace planning – tools/rag_repo/workspace.py

plan_workspace():

When there’s already a workspace path: validate it’s under repo_root via safe_subpath.

When creating default: workspace_root = safe_subpath(repo_root, tool_config.default_workspace_folder_name).

On failure: llmc-rag-repo add prints “workspace path escapes repo root” and exits non-zero.

Repo registry – tools/rag_repo/registry.py

Load entries from YAML:

repo_path = canonical_repo_path(...)

rag_workspace_path = safe_subpath(repo_path, raw_workspace_path)

If safe_subpath blows up → skip that entry and emit a clear warning / issue.

Daemon registry – tools/rag_daemon/registry.py

Keep _is_safe_path (no /etc, /proc, /sys, /dev, /root).

Add optional DaemonConfig fields:

repos_root

workspaces_root

If set, enforce with safe_subpath(repos_root, repo_path) / safe_subpath(workspaces_root, workspace_path).

Tests:

New tests/test_path_safety.py:

Unit tests for safe_subpath (normal, nested, absolute-inside, traversal, symlink-outside).

Beef up tests/test_rag_repo_workspace.py and tests/test_rag_repo_registry.py with:

Legit paths (OK).

Workspace/registry pointing outside repo root (PathTraversalError / rejected).

Trim the “demo vulnerability” section in test_error_handling_comprehensive.py and make it assert the real helper behavior instead of just dunking on Path.resolve().

2. DB & SQL Safety
This is mostly about locking in what you already did right.

Rules:

Any data that ever touches CLI / config / external systems must go into SQL via parameterized queries.

Dynamic SQL is only allowed for:

Table / column names.

Placeholder strings like "?, ?, ?".

Actions:

Quick grep + review on tools/rag/database.py and neighbors:

Where we do f"... {table} ..." or f"... ({placeholders})":

Confirm table / placeholders are internal, not user-derived.

Add tiny comments like # OK: table is internal constant so future-me doesn’t “optimize” it into a foot-gun.

Move the SQL injection test into its own module:

New file: tests/test_db_security.py

Test:

Use Database(tmp / "test.db").

Insert FileRecord with:

path="test.py'; DROP TABLE files; --"

lang="python'; DROP TABLE files; --"

Then run SELECT COUNT(*) FROM files and assert:

No exception.

Table still exists.

That gives you a pinned contract: “you don’t get to accidentally regress into SQL injection later”.

3. Subprocess Safety
You’re already doing the important part: no shell=True, commands are passed as lists.

We lock it in so it stays that way.

Where:

tools/rag/utils.py – git commands.

tools/rag_daemon/workers.py – job runner invocation.

tools/rag_nav/gateway.py – git HEAD detection.

scripts/qwen_enrich_batch.py – GPU + Ollama checks.

tools/dev/quality_baseline.py – dev tooling.

Actions:

Add tests/test_subprocess_safety.py:

Monkeypatch subprocess.run and subprocess.check_output.

Drive:

git_commit_sha(...)

git_changed_paths(...)

_invoke_runner(...)

The Ollama health check in qwen_enrich_batch.

Assert:

shell is not passed or is False.

args is a list, not a bare string.

(Optional nicety) create run_git(repo_root, args: list[str]) in tools/rag/utils.py and gradually move git calls over to it. Not required to get Phase 1 to green; just makes future audits trivial.

4. Config & Registry Validation
This is about not trusting weird YAML and failing loudly instead of shrugging.

Pieces:

Tool config validation – tools/rag_repo/config.py

Add:

@dataclass
class ConfigValidationIssue:
    field: str
    message: str
    severity: str  # "error" | "warning"
validate_tool_config(cfg: ToolConfig) -> list[ConfigValidationIssue]:

e.g. registry_path.parent doesn’t exist → warning.

(Later) invalid log level, weird types, etc.

llmc-rag-repo CLI:

Call this at startup.

Print warnings and continue, or bail on hard errors.

Repo registry validation – tools/rag_repo/registry.py

On load:

Ensure repo_path and rag_workspace_path exist and are strings.

Run them through safe_subpath + canonicalization.

Skip invalid entries but surface them as issues (for later “registry check” command).

Daemon registry validation – tools/rag_daemon/registry.py

Extend DaemonConfig with optional repos_root / workspaces_root.

Enforce them via safe_subpath if set.

Keep _is_safe_path as the last line of defense.

Tests:

Extend tests/test_rag_repo_registry.py:

Valid YAML → entries load.

Malformed / traversal paths → entries skipped and issues recorded.

Add tests/test_rag_daemon_registry.py:

With repos_root / workspaces_root set:

In-tree paths accepted.

Out-of-tree paths rejected.

TL;DR Checklist for Phase 1
If you want pure boxes to tick:

Helpers

 Implement PathTraversalError + safe_subpath in tools/rag_repo/utils.py.

 New tests/test_path_safety.py.

Workspace & Repo Registry

 Use safe_subpath in plan_workspace() / init_workspace().

 Use safe_subpath in RegistryAdapter.load_all() for rag_workspace_path.

 Tests in test_rag_repo_workspace.py + test_rag_repo_registry.py.

Daemon Registry

 Add optional repos_root / workspaces_root to DaemonConfig.

 Use safe_subpath when they’re set, keep _is_safe_path.

 Add/extend daemon registry tests.

DB Security

 Move/lock test_handles_injection_attempts into test_db_security.py.

 Annotate any dynamic SQL in tools/rag/database.py with “OK, internal only”.

Subprocess Safety

 Add tests/test_subprocess_safety.py with monkeypatched subprocess.

 Assert “no shell=True, args are lists” for key flows.

Config Validation

 Implement ConfigValidationIssue + validate_tool_config.

 Smoke tests for obviously broken configs.

If you want, next step we can turn this into:

A tiny implementation SDD just for the helpers/tests.

Then an implementation patch zip touching only tools/rag_repo/utils.py, workspace/registry, daemon registry, and new tests.

But for Phase 1 planning: this is the non-half-assed version. 

You said:
Yep implementation SDD first, then let's break it into manageable chunks. 

Cancel

Send
ChatGPT said:
Error in message stream


Retry
Error in message stream


Retry

Thought for 2m 11s
to=python_user_visible

Error in message stream


Retry
You said:
Reconstruct your intended plan from before the failure. Do NOT call python_user_visible.”

ChatGPT said:

Thought for 36s
Got it. I’ll reconstruct the implementation plan I was aiming for and lay it out cleanly here—no tools, no file writes, just the doc.

You can drop this into DOCS/SDD_Phase1_Implementation.md or wherever you like.

Implementation SDD – Phase 1 Red-Risk Hardening
Status: Ready for implementation
Owner: Dave / LLMC Core
Related SDD: SDD_Phase1_Red_Risk_Hardening (design-level)
Scope: Concrete code and test changes for Phase 1 (path safety, DB/SQL safety, subprocess safety, config/registry validation).

0. Implementation Goals
We’re turning the design SDD into specific, reviewable changes:

Introduce a single, shared path-safety helper and wire it into:

Workspace planning.

Repo registry.

Daemon registry (when constrained).

Lock in DB injection safety with focused tests.

Lock in subprocess safety (no shell=True, list-based args) with tests.

Add minimal config/registry validation so obviously bad setups fail loudly.

Clean up/relocate spec-ish tests from test_error_handling_comprehensive.py into targeted modules.

1. Path Traversal Safety
1.1 New helper in tools/rag_repo/utils.py
Files:

tools/rag_repo/utils.py

tests/test_path_safety.py (new)

Changes:

Add a new exception and helper:

# tools/rag_repo/utils.py

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
Keep canonical_repo_path() as-is (still useful), but consider internally using it as:

def canonical_repo_path(path: Path) -> Path:
    return path.expanduser().resolve()
Tests (tests/test_path_safety.py):

Add unit tests:

from pathlib import Path
import os
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
    target = base / "a/b/c.txt"
    p = safe_subpath(base, target)
    assert p == target.resolve()

def test_safe_subpath_blocks_parent_escape(tmp_path):
    base = tmp_path
    with pytest.raises(PathTraversalError):
        safe_subpath(base, "../../etc/passwd")

def test_safe_subpath_blocks_symlink_outside(tmp_path, monkeypatch):
    base = tmp_path / "root"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = base / "link"
    link.symlink_to(outside)
    with pytest.raises(PathTraversalError):
        safe_subpath(base, "link/file.txt")
(If symlinks are tricky on the platform, this last test can be marked xfail or adjusted.)

1.2 Wire safe_subpath into workspace planning
Files:

tools/rag_repo/workspace.py

tests/test_rag_repo_workspace.py (extend or create)

Current behavior (roughly):

plan_workspace(repo_root, tool_config, inspection):

Uses canonical_repo_path(repo_root) as base.

If inspection.workspace_path exists, trusts it.

Otherwise uses tool_config.default_workspace_folder_name.

New behavior:

Import new helper:

from .utils import canonical_repo_path, safe_subpath, PathTraversalError
Update plan_workspace:

def plan_workspace(repo_root: Path, tool_config: ToolConfig, inspection: RepoInspection) -> WorkspacePlan:
    base = canonical_repo_path(repo_root)

    if inspection.workspace_path is not None:
        workspace_root = safe_subpath(base, inspection.workspace_path)
    else:
        workspace_root = safe_subpath(base, tool_config.default_workspace_folder_name)

    # workspace_root / "config", etc., as before
Error handling:

Let PathTraversalError bubble up to the CLI layer where plan_workspace is called (llmc-rag-repo).

The CLI should catch it and print something like:

except PathTraversalError as e:
    logger.error("Invalid workspace path: %s", e)
    sys.exit(1)
Tests:

In tests/test_rag_repo_workspace.py:

Test: plan_workspace returns a root under repo for normal case.

Test: if inspection.workspace_path = "../outside" → PathTraversalError.

Test: default workspace name still works as before.

1.3 Wire safe_subpath into repo registry
Files:

tools/rag_repo/registry.py

tests/test_rag_repo_registry.py (extend or create)

Current behavior (approx):

repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))
rag_workspace_path = canonical_repo_path(Path(os.path.expanduser(data["rag_workspace_path"])))
New behavior:

from .utils import canonical_repo_path, safe_subpath, PathTraversalError

repo_path = canonical_repo_path(Path(os.path.expanduser(data["repo_path"])))
try:
    rag_workspace_path = safe_subpath(repo_path, data["rag_workspace_path"])
except PathTraversalError as e:
    # skip entry, but record issue
    logger.warning("Skipping registry entry for %s: %s", repo_path, e)
    return None  # or drop this record according to existing patterns
If the YAML allows missing rag_workspace_path, either:

Fallback to default under repo, via safe_subpath(repo_path, default_name), or

Mark as invalid.

Tests:

Valid entry: repo + workspace under repo → accepted.

Invalid entry: workspace outside repo → entry skipped / not returned.

Registry loader should be deterministic: invalid entries don’t crash registry load.

1.4 Daemon registry constraints
Files:

tools/rag_daemon/config.py (or wherever DaemonConfig lives)

tools/rag_daemon/registry.py

tests/test_rag_daemon_registry.py (new or extend)

Implementation:

Extend daemon config:

from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class DaemonConfig:
    # existing fields...
    repos_root: Optional[Path] = None
    workspaces_root: Optional[Path] = None
In RegistryClient.load() (or wherever entries are normalized):

After loading raw repo_path / rag_workspace_path:

from tools.rag_repo.utils import safe_subpath, PathTraversalError

if config.repos_root is not None:
    repo_path = safe_subpath(config.repos_root, raw_repo_path)
else:
    repo_path = Path(raw_repo_path).expanduser().resolve()

if config.workspaces_root is not None and raw_workspace_path is not None:
    rag_workspace_path = safe_subpath(config.workspaces_root, raw_workspace_path)
else:
    rag_workspace_path = Path(raw_workspace_path).expanduser().resolve()
Preserve _is_safe_path checks after this for system dir bans.

Tests:

With repos_root set:

Repo inside root → accepted.

Repo outside root → rejected or raises clearly.

Similarly for workspaces_root.

2. DB & SQL Safety
Files:

tools/rag/database.py

tests/test_db_security.py (new)

tests/test_error_handling_comprehensive.py (trim)

2.1 Audit (implementation steps)
Search in tools/rag/database.py and siblings for:

f"SELECT

f"INSERT

f"UPDATE

f"DELETE

For each dynamic SQL site:

If using only internal table/column names → keep, add a short comment:

# OK: table name is from internal enum, not user input
If any user/config text is interpolated directly → refactor to param-based:

# BAD:
sql = f"SELECT * FROM files WHERE path = '{path}'"
conn.execute(sql)

# GOOD:
sql = "SELECT * FROM files WHERE path = ?"
conn.execute(sql, (path,))
(If you already did this, the audit just confirms and documents.)

2.2 Injection test
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
        # fill any required fields with minimal valid data
    )
    db.upsert_file(rec)

    # If injection worked, this would raise an OperationalError
    cursor = db.conn.execute("SELECT COUNT(*) FROM files")
    (count,) = cursor.fetchone()
    assert count >= 1
Clean up:

Remove or simplify test_handles_injection_attempts in test_error_handling_comprehensive.py to avoid duplication.

3. Subprocess Safety
Files:

tools/rag/utils.py

tools/rag_daemon/workers.py

tools/rag_nav/gateway.py

scripts/qwen_enrich_batch.py

tools/dev/quality_baseline.py

tests/test_subprocess_safety.py (new)

3.1 Confirm no shell=True
Implementation:

One-time grep for subprocess.run / subprocess.check_output.

Ensure all call sites:

Use list arguments.

Don’t set shell=True (and if they do, remove/replace).

3.2 Tests
New file: tests/test_subprocess_safety.py

Pseudo-structure:

import subprocess
from pathlib import Path

import pytest

import tools.rag.utils as rag_utils
from tools.rag_daemon import workers
from tools.rag_nav import gateway

def _assert_no_shell_and_list_args(calls):
    for args, kwargs in calls:
        # args[0] is the command list in subprocess.run
        cmd = args[0]
        assert isinstance(cmd, (list, tuple)), "Expected list args for subprocess"
        assert not kwargs.get("shell"), "shell=True must not be used"

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

    repo_root = tmp_path
    # call whatever helper you use to get commit SHA, changed files, etc.
    _ = rag_utils.git_commit_sha(repo_root)

    _assert_no_shell_and_list_args(calls)

def test_daemon_invoke_runner_uses_safe_subprocess(monkeypatch, tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    # construct minimal test config/repo descriptor and call _invoke_runner
    # or public wrapper if exists

    _assert_no_shell_and_list_args(calls)
Adjust the called helpers to match your actual APIs (git_commit_sha, _invoke_runner, etc.).

4. Config & Registry Validation
Files:

tools/rag_repo/config.py

tools/rag_repo/registry.py

(Optionally) CLI entrypoint module for llmc-rag-repo

tests/test_rag_repo_config.py

tests/test_rag_repo_registry.py (used above)

4.1 Tool config validation
In tools/rag_repo/config.py:

Add:

from dataclasses import dataclass
from typing import List

@dataclass
class ConfigValidationIssue:
    field: str
    message: str
    severity: str  # "error" | "warning"
And:

def validate_tool_config(cfg: ToolConfig) -> list[ConfigValidationIssue]:
    issues: list[ConfigValidationIssue] = []

    # Example checks; expand as needed
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

    return issues
CLI integration:

Wherever the CLI loads ToolConfig (e.g., main() for llmc-rag-repo):

cfg = load_tool_config(config_path)
issues = validate_tool_config(cfg)

errors = [i for i in issues if i.severity == "error"]
for issue in issues:
    log_fn = logger.error if issue.severity == "error" else logger.warning
    log_fn("Config issue (%s): %s - %s", issue.severity, issue.field, issue.message)

if errors:
    sys.exit(1)
Tests (tests/test_rag_repo_config.py):

Minimal tests:

from tools.rag_repo.config import ToolConfig, validate_tool_config

def test_validate_tool_config_missing_registry_path_is_error(tmp_path):
    cfg = ToolConfig(
        registry_path=None,
        # other fields minimal valid
    )
    issues = validate_tool_config(cfg)
    assert any(i.severity == "error" and i.field == "registry_path" for i in issues)
And one “warning only” case.

5. Test Suite Refactor (Phase 1-Scope Only)
File:

tests/test_error_handling_comprehensive.py

Changes:

For path traversal:

Either remove the “vulnerability demo” test or:

Rewrite to call safe_subpath and assert it raises PathTraversalError on malicious paths.

For SQL injection:

Remove or simplify, since tests/test_db_security.py is the canonical test.

Ensure remaining tests in this file either:

Directly exercise real code paths, or

Are marked xfail(strict=True) with clear reasons.

Goal: this file becomes bonus coverage, not the only place where important guarantees live.

6. Implementation Order
If you want a sane commit/patch order:

Commit 1 – Helpers & path safety tests

PathTraversalError + safe_subpath.

tests/test_path_safety.py.

Commit 2 – Workspace + repo registry wiring

plan_workspace changes.

RegistryAdapter changes.

Updated tests.

Commit 3 – Daemon registry constraints

DaemonConfig extension.

RegistryClient.load() path enforcement.

New daemon registry tests.

Commit 4 – DB security test + small SQL comments

tests/test_db_security.py.

Audit & comments in database.py.

Commit 5 – Subprocess safety tests

tests/test_subprocess_safety.py.

Any small tweaks to subprocess calls (if needed).

Commit 6 – Config validation + tests

ConfigValidationIssue, validate_tool_config.

CLI integration.

Config tests.

Commit 7 – Cleanup of test_error_handling_comprehensive.py

Trim/move spec-like tests to targeted modules.

When you’re ready, next step is: we package one patch zip (e.g. llmc_phase1_security_patch_v1.zip) with:

These code changes in proper hierarchy.

This SDD + the higher-level Phase 1 SDD.

A short agent prompt for implementation review / test execution.

Then you just drop it into ~/src/llmc, unzip, and review git diff like a sane person.

You said:
We just tried that and it bombed the fuckout.  Let's do a SDD alone first.
ChatGPT said:

Thought for 25s
Yeah, fair. Let’s stop juggling zips and just nail the SDD cleanly first.

Here’s a standalone Implementation SDD for Phase 1 – Red-Risk Hardening. You can drop this as
DOCS/SDD_Phase1_Red_Risk_Hardening_Implementation.md in the repo.

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

---

There you go. One paste into a `.md` file and you’ve got your Implementation SDD without fighting the tooling gods.
You said:
Ok, it didn't actually give me a link to click it.. I copied it pasted to word as text only then copied that and pasted it to a SDD file.. geez lol.  Give me a breakout of steps I can work through that will be small enough to be done without breaking, aka 15 minute GPT tasks.  
ChatGPT said:

Thought for 19s
Yeah that pipeline was… not elegant. 🧯
Alright, let’s treat this like a Kanban board for you + an LLM, with bite-sized 15-minute chunks.

I’ll give you:

A sequence of small tasks (each should be 1 LLM patch session).

For each: Scope, Files, What to ask GPT, and How to sanity-check.

You can literally copy the “Prompt” into your code agent (Claude, Codex, whatever) and go.

Group 1 – Path Helper & Direct Tests
Task 1 – Add PathTraversalError + safe_subpath
Goal: Introduce the helper, no wiring yet.

Scope:

tools/rag_repo/utils.py

NEW: tests/test_path_safety.py

Prompt to your code agent:

Implement a new PathTraversalError exception and a safe_subpath(base, user_path) helper in tools/rag_repo/utils.py.

Requirements:

PathTraversalError subclasses ValueError.

safe_subpath:

Accepts base: Path, user_path: str | Path.

Expands ~ in user input.

Resolves both base and candidate with .expanduser().resolve().

If user_path is absolute and not under base, raise PathTraversalError.

If relative, join base / user_path, resolve, then ensure candidate.relative_to(base_resolved) succeeds.

On failure, raise PathTraversalError with a clear message.

Add a new test module tests/test_path_safety.py with unit tests for:

Normal relative path under base.

Relative path using .. that still stays under base.

Absolute path inside base.

A .. path that escapes base → raises PathTraversalError.

Do not wire this helper into any other modules yet. Just implement helper + tests.

Sanity check:

pytest tests/test_path_safety.py
Task 2 – Optional: Add symlink safety test
Goal: Lock down behavior with symlinks, if your platform cooperates.

Scope:

tests/test_path_safety.py only.

Prompt:

In tests/test_path_safety.py, add a test that verifies safe_subpath blocks a symlink that points outside the base directory.

Create base = tmp_path / "root", outside = tmp_path / "outside".

Make outside a real directory, link = base / "link", and link.symlink_to(outside).

Call safe_subpath(base, "link/file.txt") and assert it raises PathTraversalError.

If the platform doesn’t support symlinks well, you can mark this test xfail with a clear reason.

Sanity:

pytest tests/test_path_safety.py -k symlink
Group 2 – Wire Path Safety into Repo Tools
Task 3 – Wire into plan_workspace
Goal: Workspaces can’t escape the repo root.

Scope:

tools/rag_repo/workspace.py

tests/test_rag_repo_workspace.py (or create if missing)

Prompt:

Update tools/rag_repo/workspace.py to use the new safe_subpath helper for determining the workspace root.

Changes:

Import safe_subpath and PathTraversalError from tools.rag_repo.utils.

In plan_workspace(repo_root, tool_config, inspection):

Resolve base = canonical_repo_path(repo_root).

If inspection.workspace_path is not None, compute workspace_root = safe_subpath(base, inspection.workspace_path).

Otherwise, compute workspace_root = safe_subpath(base, tool_config.default_workspace_folder_name).

Do not change how subdirs under workspace_root are built.

Add/modify tests in tests/test_rag_repo_workspace.py:

Normal case: workspace under repo root works as before.

Malicious case: inspection.workspace_path = "../outside" → PathTraversalError is raised.

Do not change any CLI behavior yet; just the workspace planning + tests.

Sanity:

pytest tests/test_rag_repo_workspace.py tests/test_path_safety.py
Task 4 – Wire into repo registry loader
Goal: Bad workspace paths in registry are rejected.

Scope:

tools/rag_repo/registry.py

tests/test_rag_repo_registry.py

Prompt:

Update tools/rag_repo/registry.py to validate rag_workspace_path using safe_subpath.

Implementation:

Import safe_subpath and PathTraversalError.

When constructing a RegistryEntry from YAML:

Resolve repo_path via canonical_repo_path(...) as today.

Read raw_workspace = data.get("rag_workspace_path").

If raw_workspace is not None:

Try rag_workspace_path = safe_subpath(repo_path, raw_workspace).

On PathTraversalError, log a warning and skip this entry (return None or equivalent so it doesn’t appear in the registry).

If raw_workspace is None:

Use safe_subpath(repo_path, DEFAULT_WORKSPACE_FOLDER_NAME) for the workspace.

Tests in tests/test_rag_repo_registry.py:

Valid entry: repo path + workspace under repo root → entry is loaded.

Invalid entry: workspace path with ../.. → entry is skipped / not returned.

Verify with assertions on the collection returned from the registry loader.

Sanity:

pytest tests/test_rag_repo_registry.py
Task 5 – Add daemon config constraints (repos_root, workspaces_root)
Goal: Daemon can optionally enforce “all repos/workspaces live under these roots”.

Scope:

tools/rag_daemon/config.py (or wherever DaemonConfig lives)

tools/rag_daemon/registry.py

NEW/updated: tests/test_rag_daemon_registry.py

Prompt:

Extend daemon configuration and registry to optionally constrain repo/workspace locations.

In the daemon config dataclass (DaemonConfig), add:

repos_root: Optional[Path] = None

workspaces_root: Optional[Path] = None

In tools/rag_daemon/registry.py, add a helper like _normalize_paths(config, raw_repo_path, raw_workspace_path) which:

If config.repos_root is set, uses safe_subpath(config.repos_root, raw_repo_path) to compute repo_path.

Else, resolves raw_repo_path as today.

Similarly, if config.workspaces_root is set and raw_workspace_path is not None, uses safe_subpath(config.workspaces_root, raw_workspace_path).

Otherwise, resolves raw_workspace_path as today.

Returns (repo_path, workspace_path).

Keep _is_safe_path checks after normalization so /etc, /proc, etc. are still rejected.

Add tests/test_rag_daemon_registry.py:

When repos_root is set and repo path is inside it → entry is accepted.

When repos_root is set and repo path is outside it → entry is rejected or raises PathTraversalError that is handled in a controlled way.

Same idea for workspaces_root.

Sanity:

pytest tests/test_rag_daemon_registry.py
Group 3 – DB / SQL Safety
Task 6 – Add DB injection regression test
Goal: Pin the “no SQL injection” behavior.

Scope:

NEW: tests/test_db_security.py

Prompt:

Create tests/test_db_security.py that verifies SQL injection attempts via file path/lang cannot drop the files table.

Use the existing Database and FileRecord APIs from tools.rag/database.py.

In the test:

Create a new temporary DB file with Database(tmp_path / "index.db").

Insert a FileRecord with:

path = "test.py'; DROP TABLE files; --"

lang = "python'; DROP TABLE files; --"

and minimal valid values for all required fields.

After insertion, run SELECT COUNT(*) FROM files directly on db.conn and assert:

The query succeeds.

There is at least 1 row.

Do not modify tools/rag/database.py yet, just add the test.

Sanity:

pytest tests/test_db_security.py
Task 7 – Audit tools/rag/database.py and fix any unsafe SQL
Goal: Ensure user/config data never gets string-interpolated into SQL.

Scope:

tools/rag/database.py

Re-run tests/test_db_security.py

Prompt:

Audit tools/rag/database.py for dynamic SQL and ensure all user/config-derived values are passed as parameters, not interpolated into SQL strings.

Steps:

Search for f"SELECT, f"INSERT, f"UPDATE, f"DELETE, or any execute calls with direct string formatting.

For each location:

If only table/column names or fixed placeholders are dynamic (internal constants), keep as-is but add a comment like:
# OK: table/column names are internal, not user-controlled.

If any values can come from user/config (paths, file names, language, text fields), refactor to use SQL parameters:

e.g., "SELECT * FROM files WHERE path = ?" with a params tuple.

After changes, run pytest tests/test_db_security.py and ensure it still passes.

Sanity:

pytest tests/test_db_security.py
Group 4 – Subprocess Safety
Task 8 – Subprocess safety tests for git helpers
Goal: Lock in “no shell=True, list args” for core git utilities.

Scope:

NEW: tests/test_subprocess_safety.py

Read-only usage of tools/rag/utils.py

Prompt:

Create tests/test_subprocess_safety.py to enforce safe subprocess patterns for git helper functions.

Monkeypatch subprocess.run to capture arguments.

Call one or more git helper functions from tools.rag.utils (e.g. git_commit_sha, git_changed_paths or whatever exists).

In the fake run, record args and kwargs and return a dummy result.

After calling the helper, assert:

The first positional arg to subprocess.run is a list or tuple of strings.

shell is not present or is False in kwargs.

Do not change production code yet; just add the test.

Sanity:

pytest tests/test_subprocess_safety.py -k git
Task 9 – Subprocess safety tests for daemon runner / enrich scripts
Goal: Same guarantees for daemon + enrich flows.

Scope:

tests/test_subprocess_safety.py (extend)

Read-only usage of:

tools/rag_daemon/workers.py

scripts/qwen_enrich_batch.py (or similar)

Prompt:

Extend tests/test_subprocess_safety.py to cover:

The daemon worker runner (_invoke_runner or its public wrapper).

Any entry point in scripts/qwen_enrich_batch.py that calls subprocess.run or check_output.

For each:

Monkeypatch subprocess.run / check_output to record the calls.

Trigger the minimal possible call into the function (mock configs or arguments as needed).

Assert:

shell is not used.

The command is passed as a list or tuple, not a raw string.

If any production call sites fail these tests, refactor them to follow the same safe pattern and re-run the tests.

Sanity:

pytest tests/test_subprocess_safety.py
Group 5 – Config Validation + Cleanup
Task 10 – Add ConfigValidationIssue + validate_tool_config
Goal: Minimal config sanity check.

Scope:

tools/rag_repo/config.py

NEW: tests/test_rag_repo_config.py

Prompt:

Implement a minimal tool config validation API.

In tools/rag_repo/config.py:

Add a ConfigValidationIssue dataclass with fields:

field: str

message: str

severity: str ("error" or "warning")

Implement validate_tool_config(cfg: ToolConfig) -> list[ConfigValidationIssue] with at least:

If cfg.registry_path is None or empty → add an "error" issue.

Else if cfg.registry_path.parent does not exist → add a "warning" issue.

Create tests/test_rag_repo_config.py with tests:

Missing registry_path → has an "error" for field "registry_path".

Non-existent parent dir → has a "warning" for field "registry_path".

Sanity:

pytest tests/test_rag_repo_config.py
Task 11 – Wire validate_tool_config into CLI
Goal: Fail fast on obviously broken config.

Scope:

CLI module that loads ToolConfig (e.g., tools/rag_repo/cli.py or equivalent)

Prompt:

Integrate validate_tool_config into the llmc-rag-repo CLI startup.

After loading ToolConfig, call validate_tool_config(cfg).

Log all issues:

"error" via logger.error.

"warning" via logger.warning.

If there are any "error" issues, exit the process with a non-zero exit code.

Ensure this behavior is covered by an existing or new CLI-level test:

With a missing registry path → CLI should fail early with an error.

With only a nonexistent parent dir → CLI should log a warning but continue.

Sanity: (whatever you use for CLI tests, plus):

pytest tests/test_rag_repo_config.py
Task 12 – Clean up test_error_handling_comprehensive.py
Goal: Stop that file from being the “everything and nothing” bucket.

Scope:

tests/test_error_handling_comprehensive.py

Prompt:

Refactor tests/test_error_handling_comprehensive.py for Phase 1:

Remove or simplify any path traversal tests that only demonstrate Path.resolve vulnerabilities and do not call real LLMC helpers. If you keep a path traversal test, make it call safe_subpath and assert that malicious inputs raise PathTraversalError.

Remove or simplify any SQL injection tests that duplicate test_db_security.py behavior. Keep at most a thin smoke test if needed.

Any remaining tests that don’t touch real LLMC code and only assert trivial truths should be:

Deleted, or

Marked with @pytest.mark.xfail(strict=True, reason="spec-only; behavior enforced in dedicated tests").

Goal: after this change, the real guarantees about path safety, SQL safety, and subprocess behavior live in focused test modules, and this file is supplementary.

Sanity:

pytest tests/test_error_handling_comprehensive.py
pytest  # full run if you have patience
If you want, next step after you knock out a couple of these is:
we pick the next 1–2 tasks, and I’ll help you craft ultra-tight, repo-aware prompts for your actual patch agent (including “don’t stomp unrelated code” rules, git hygiene, etc.).





No file chosenNo file chosen
ChatGPT can make mistakes. Check important info.
Activity
·
19s

Thinking
Structuring small steps for user tasks
The user wants small, manageable steps for LLM patching, each task under 15 minutes. They need clear, concrete tasks where no web browsing is required, just instructions based on their local repo. Steps should be structured with scope, files touched, expected outcomes, and fun prompts.

Aligning with implementation tasks
I'll break the tasks into clear phases, like "Phase 1A: Path helper," with 10-15 tasks, each well-defined for 15-minute work sessions. Each task will be concise but complete, with deliverables, commands to run, and clear instructions for the coding agent. No tools involved, just structured tasks for easy tracking.

Proposing structured 15-minute tasks
To address earlier preferences without overcomplicating things, I'll propose small tasks like:
Chunk 1: Create helper + tests skeleton
Task 1a: Research current usage. Task 1b: Implement helper in utils. Task 1c: Add new test file.

Each task will be short enough to fit the 15-minute work window, focusing on clear steps followed by patching and running tests. This approach should work well without going overboard.

Thought for 19s
Done



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

 