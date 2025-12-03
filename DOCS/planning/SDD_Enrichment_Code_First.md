SDD - LLMC Enrichment Runner (Code-First Prioritization)
Version: 0.1
Date: 2025-12-02
Owner: LLMC
Status: Draft for implementation review

**📄 Related:** [`SDD_Enrichment_Path_Weights.md`](SDD_Enrichment_Path_Weights.md) - Configurable path-based prioritization

======================================================================
0. PURPOSE AND SCOPE

0.1 Purpose

This SDD defines changes to the LLMC enrichment runner so that it:

Prioritizes enrichment of code-related files before other content.

Uses existing LLMC metadata (file paths, content_type, etc.) instead of ad hoc heuristics wherever possible.

Remains compatible with current enrichment DB schema and routing design.

Provides visible, testable behavior change without a large rewrite of the enrichment pipeline.

0.2 In Scope

Enrichment runner scheduling and prioritization logic.

Classification of files into "code" vs "non-code".

A code-first backlog and batching model.

CLI and programmatic options to control prioritization behavior.

Telemetry and metrics around code-first enrichment.

0.3 Out of Scope

New enrichers or model backends.

Changes to enrichment content routing (that logic is reused).

Large DB schema migrations.

Multi-host or distributed scheduling.

======================================================================

CONTEXT AND ASSUMPTIONS
======================================================================

1.1 Current State (High Level)

LLMC has an enrichment subsystem that:

Scans repo files.

Stores spans / embeddings / metadata in a SQLite RAG DB.

Uses an enrichment router to pick which enrichers to apply.

Enrichment runner currently treats eligible files mostly uniformly:

It computes a backlog of "things to enrich".

It processes them using roughly FIFO or basic ordering.

The enrichment DB (e.g. "enrichments" table) now tracks content_type and content_language, which allows us to distinguish code vs non-code without re-parsing every file.

1.2 Problem

On a large mixed repo (code + docs + configs), initial enrichment can:

Spend a lot of budget and time on non-code files.

Delay enrichment of core code modules that are most useful for code assistance, refactor tools, and RAG for source code.

The user experience for code-focused tasks (refactors, code-level Q&A) is worse until code files are enriched.

1.3 Assumptions

The enrichment DB schema already contains:

Some representation of file identity (repo path or file_id).

Content type and possibly language for each enrichment row.

The enrichment runner can access both:

RAG DB.

On-disk repo files.

The enrichment runner is invoked via CLI and internal APIs.

The new prioritization should be backward compatible:

If disabled, behavior is equivalent to current runner.

======================================================================
2. FUNCTIONAL REQUIREMENTS

FR1: The enrichment runner shall compute a backlog that distinguishes:
- Code files (primary).
- Non-code files (secondary).

FR2: By default, the enrichment runner shall schedule code-related files
before non-code files for new or stale enrichments.

FR3: The runner shall provide a CLI flag and programmatic option:
- --code-first (default: true)
- --no-code-first (to disable and revert to old behavior)

FR4: The runner shall respect existing routing and configuration:
- It must not bypass or hard code which enrichers to use.
- It only changes ordering and batching.

FR5: The runner shall expose a dry-run mode that prints the planned
enrichment order with classification (code vs non-code).

FR6: The runner shall avoid starving non-code files:
- It must eventually process non-code backlog when code backlog
is low or after a configurable ratio.

FR7: The runner shall be able to limit concurrent jobs:
- Max concurrent enrichments for code files.
- Max concurrent enrichments overall (shared limit).

FR8: The runner shall emit telemetry events and counters:
- Number of code vs non-code files enriched.
- Queue depth by class.
- Time-to-first-enrichment for code files in a fresh repo.

======================================================================
3. NON-FUNCTIONAL REQUIREMENTS

NFR1: Code-first rules must not significantly increase DB or FS load
compared to current runner.

NFR2: The enrichment runner SHALL respect path_weight ordering such that,
absent concurrency effects, no file with weight W is enriched before all
files with weight ≤ W-2 are complete, unless the higher-priority queue
is exhausted or the starvation ratio is reached.

> Note: Original NFR2 was percentage-based ("80% of first N should be code")
> which failed when repos are doc-heavy. Replaced with weight-based guarantee.
> See SDD_Enrichment_Path_Weights.md for details.

NFR3: Enrichment runner must remain robust to partial scans, missing
files, or DB inconsistencies; code-first logic must degrade
gracefully.

NFR4: Implementation should be incremental and shippable in one or two
small patches.

======================================================================
4. ARCHITECTURE OVERVIEW

4.1 High-Level Design

We introduce a "Code-First Scheduler" inside the existing enrichment
runner. The scheduler:

Generates a backlog of enrichment tasks from:

DB metadata (enrichments + file index).

File system scan (for new files).

Classifies tasks using configurable path weights (see SDD_Enrichment_Path_Weights.md).

Computes a priority score per task using:
  - Content type base priority (CODE=100, NON_CODE=10)
  - Path weight multiplier: `final = base * (11 - weight) / 10`
  - Modifiers (new file, recently changed, etc.)

Uses a priority queue to pop tasks in weight-respecting order.

4.2 Components

New or modified components:

EnrichmentBacklogBuilder

Generates the set of candidate enrichment tasks.

FileClassifier

Classifies file paths using path weights config.
Falls back to content_type + extension heuristics.

CodeFirstScheduler

Maintains priority queues and picks next tasks.

RunnerController

Applies concurrency limits and monitors progress.

TelemetryIntegration

Records weight-stratified metrics.

Existing components reused:

EnrichmentRouter

Enrichers (LLM calls, parsing, etc.)

RAG DB access layer

Logging

======================================================================
5. DATA MODEL AND CLASSIFICATION

5.1 Task Model

EnrichmentTask:

file_path: str

file_id: str or int (if available from DB)

content_type: str or None (e.g. "text/x-python", "text/markdown")

language: str or None (e.g. "python", "bash", "markdown")

path_weight: int (1-10, from config)

priority: float (computed from base + weight + modifiers)

last_enriched_at: datetime or None

needs_refresh: bool

5.2 Path Weight Configuration

See SDD_Enrichment_Path_Weights.md for full specification.

Key points:
- Weight 1-10 scale (lower = higher priority)
- Glob patterns in [enrichment.path_weights] config section
- Collision resolution: highest weight wins (pessimistic)
- Default weight 5 for unmatched files

5.3 Priority Scoring

Each task gets a priority score:

Base (from content type):

CODE: base_priority = 100

NON_CODE: base_priority = 10

Path weight multiplier:

priority = base_priority * (11 - path_weight) / 10

Additional modifiers:

New file (never enriched): +50

Recently changed (file mtime > last_enriched_at): +30

Under explicit code directories with weight 1-2: +20

Final:

priority = (base_priority * (11 - path_weight) / 10) + modifiers

Priority is capped to a reasonable range, for example 0..200.

======================================================================
6. ENRICHMENT RUNNER FLOW

6.1 Backlog Construction

Steps:

Enumerate candidate files:

From DB: files known to LLMC (file index).

From repo scan: new files not yet known in DB.

For each candidate:

Lookup existing enrichment metadata (last_enriched_at, content_type,
language).

Determine if enrichment is needed:

Never enriched.

File content hash changed.

Enrichment version or schema changed.

For each needed file:

Compute path_weight from config.

Compute priority score.

Build single priority queue sorted by priority (descending).

6.2 Scheduling Policy

When --code-first is enabled:

Runner pops tasks from priority queue in order.

Starvation prevention via configured ratio:

Example: for every 5 high-priority (weight ≤ 3) tasks,
schedule 1 low-priority (weight > 5) task.

When --no-code-first is enabled:

Runner treats all tasks uniformly:

Single queue with priority purely based on age / changes.

Or older policy, as currently implemented.

6.3 Concurrency Model

Configuration:

max_concurrent_enrichments (global)

max_concurrent_high_priority (weight ≤ 3)

max_concurrent_low_priority (weight > 5, optional)

Scheduler ensures:

At any time:

running_high <= max_concurrent_high_priority

running_total <= max_concurrent_enrichments

6.4 Dry Run Mode

CLI flag: --dry-run

Additional flag: --show-weights

Behavior:

Build backlog as normal, but do not execute enrichment.

Print or log:

Top N planned tasks with their weight, priority, and matched patterns.

Summary counts by weight tier.

======================================================================
7. CLI AND CONFIGURATION

7.1 CLI Additions

Existing command (example):

llmc enrich run [options]

New options:

--code-first / --no-code-first
Default: --code-first.

--starvation-ratio HIGH:LOW
For every HIGH high-priority tasks, schedule 1 low-priority.
Default: 5:1

--dry-run
Build and display backlog but do not call enrichers.

--show-weights
Include weight and pattern match info in output.

--max-high-concurrent N
Set max concurrent high-priority tasks (optional override).

7.2 Configuration

llmc.toml:

[enrichment.runner]
code_first_default = true
starvation_ratio_high = 5
starvation_ratio_low = 1
max_concurrent = 4
max_concurrent_high_priority = 4

[enrichment.path_weights]
# See SDD_Enrichment_Path_Weights.md for full config
"src/**"        = 1
"lib/**"        = 1
"**/tests/**"   = 6
"docs/**"       = 8
"vendor/**"     = 10

CLI flags override config values for a single run.

======================================================================
8. TELEMETRY AND OBSERVABILITY

8.1 Metrics

Per run and over time:

enrichment.files_enriched_by_weight[1-10]

enrichment.queue_depth_by_weight_tier (high/medium/low)

enrichment.time_to_first_high_priority

enrichment.time_to_all_high_priority (if computed)

enrichment.runner_mode ("code_first" or "legacy")

8.2 Logging

At runner start:

Log configuration (code_first, weights, limits).

Log backlog summary:

"Backlog: X high-priority (w≤3), Y medium (w4-6), Z low (w>6), mode=code_first".

Per batch:

Log scheduled tasks with weights.

Log completion events with duration and outcome.

8.3 Introspection

Optional: MCP tools or CLI commands:

llmc enrich status

Shows current queues by weight tier, running tasks, and configuration.

llmc enrich plan --show-weights

Dry run with full weight breakdown.

======================================================================
9. ERROR HANDLING

9.1 File Level Errors

If a file is missing or unreadable:

Mark task as failed with error reason.

Log warning and continue.

Should not block other tasks.

9.2 DB Errors

If RAG DB write fails or is busy:

Use existing DB error handling.

Consider integration with anti-stomp / MAASL if present.

Retry once or fail task with clear status.

9.3 Classification Errors

If path weight config is malformed:

Log error and use default weight (5).

If content_type or language are unknown:

Use default weight and base priority.

9.4 Configuration Errors

Invalid weights (outside 1-10):

Log error and clamp to valid range.

Conflicting flags (for example both --code-first and --no-code-first):

CLI should fail fast with usage error.

======================================================================
10. INTERACTIONS WITH OTHER SYSTEMS

10.1 Anti-Stomp / MAASL

When integrated with MAASL:

Enrichment runner should invoke enrichers through stomp-guarded
APIs, especially for DB and graph writes.

Path weight prioritization does not change lock semantics; it only
changes which tasks get scheduled first.

10.2 RAG Query Path

Earlier enrichment of high-priority (low-weight) files will:

Improve quality of code-related RAG answers sooner.

Existing RAG query code does not need to change.

10.3 Docgen

Code-first enrichment may be paired with code-first docgen in future
phases, but this SDD does not change docgen behavior.

======================================================================
11. TESTING STRATEGY

11.1 Unit Tests

FileClassifier / Path Weights:

Single pattern matching.

Collision resolution (highest weight wins).

Default weight for unmatched files.

Priority scoring:

Check scores for different weight + content type combinations.

Check modifiers (new, changed).

CodeFirstScheduler:

Correct ordering of tasks by priority.

Non-starvation at configured ratios.

11.2 Integration Tests

Scenario: Mixed repo with:

50 code files (src/, app/) - weight 1.

30 test files (src/tests/) - weight 6.

20 doc files (docs/, markdown) - weight 8.

Run enrichment with --code-first:

Assert that all weight-1 files complete before weight-6.

Assert that weight-6 files complete before weight-8.

Assert starvation ratio is respected.

Run enrichment with --no-code-first:

Assert older / default ordering is preserved.

Dry run with --show-weights:

Validate backlog output shows correct weights and priorities.

11.3 Performance Tests

Large repo (thousands of files).

Measure time to:

Build backlog and compute weights.

Start first high-priority enrichment.

Ensure overhead from weight computation remains acceptable.

======================================================================
12. ROLLOUT PLAN

Phase 1: Path weights and priority scoring

Implement path weight config and collision resolution.

Update FileClassifier to compute weights.

Wire priority formula into scheduler.

Implement --dry-run and --show-weights.

Leave code_first_default disabled in config.

Phase 2: Default code-first and metrics

Turn code_first_default on in config.

Add telemetry counters stratified by weight tier.

Verify behavior on real repos.

Phase 3: Fine tuning and integration with anti-stomp

If MAASL is available, wrap enrichment writes via stomp-guard APIs.

Tune default weights and ratios based on real usage.

End of SDD.