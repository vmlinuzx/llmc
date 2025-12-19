"""
Enrichment Pipeline - Clean orchestration for batch enrichment.

This module provides the EnrichmentPipeline class which coordinates:
- Span selection (pending enrichments from DB)
- Chain selection (via EnrichmentRouter)
- Backend execution (via BackendCascade)
- Result persistence (DB writes)
- Metrics/logging (JSONL events)

Usage:
    from llmc.rag.enrichment_pipeline import EnrichmentPipeline
    from llmc.rag.enrichment_factory import create_backend_from_spec

    pipeline = EnrichmentPipeline(
        db=database,
        router=enrichment_router,
        backend_factory=create_backend_from_spec,
        prompt_builder=build_enrichment_prompt,
    )

    result = pipeline.process_batch(limit=50)
    print(f"Enriched {result.succeeded}/{result.attempted} spans")
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import sys
import time
from typing import Any, Protocol

from llmc.rag.config_enrichment import EnrichmentBackendSpec
from llmc.rag.database import Database
from llmc.rag.enrichment_backends import (
    AttemptRecord,
    BackendAdapter,
    BackendCascade,
    BackendError,
)
from llmc.rag.enrichment_router import (
    EnrichmentRouteDecision,
    EnrichmentRouter,
    EnrichmentSliceView,
)


class BackendFactory(Protocol):
    """Factory protocol for creating backend adapters from specs."""

    def __call__(self, spec: EnrichmentBackendSpec) -> BackendAdapter: ...


@dataclass
class EnrichmentResult:
    """Result of enriching a single span."""

    span_hash: str
    success: bool
    enrichment: dict[str, Any] | None
    attempts: list[AttemptRecord]
    route_decision: EnrichmentRouteDecision
    duration_sec: float
    error: str | None = None


@dataclass
class EnrichmentBatchResult:
    """Summary of a batch enrichment run."""

    total_pending: int
    attempted: int
    succeeded: int
    failed: int
    skipped: int
    duration_sec: float
    results: list[EnrichmentResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.attempted == 0:
            return 0.0
        return self.succeeded / self.attempted


def build_enrichment_prompt(item: dict[str, Any], repo_root: Path | None = None) -> str:
    """Build enrichment prompt from span item.

    Reads prompt template from [enrichment.prompt].template in llmc.toml if available,
    otherwise uses a default terse prompt suitable for Qwen3.

    Args:
        item: Span data dict with path, lines, code_snippet, etc.
        repo_root: Optional repo root for loading config.

    Returns:
        Formatted prompt string ready for LLM
    """
    from llmc.rag.config import load_config

    # Try to load prompt from config
    template = None
    try:
        cfg = load_config(repo_root)
        template = cfg.get("enrichment", {}).get("prompt", {}).get("template")
    except Exception:
        pass  # Use default
    path = item.get("path", item.get("file_path", ""))
    line_start, line_end = item.get("lines", item.get("line_range", [0, 0]))
    snippet = item.get("code_snippet", item.get("content", ""))

    # Ensure we have valid line numbers
    if not isinstance(line_start, int) or not isinstance(line_end, int):
        line_start, line_end = 0, 0

    # Use config template or default terse prompt
    if template:
        # Format the template with our variables
        prompt = template.format(
            path=path,
            line_start=line_start,
            line_end=line_end,
            snippet=snippet,
        )
    else:
        # Default terse prompt (suitable for Qwen3 4B which is verbose)
        prompt = f"""Return ONLY ONE VALID JSON OBJECT in ENGLISH.
No markdown, no comments, no extra text.
BE TERSE. Minimum words. No filler.

Output format (keys are FIXED):
{{"summary_120w":"...","inputs":["..."],"outputs":["..."],
"side_effects":["..."],"pitfalls":["..."],
"usage_snippet":"...","evidence":[{{"field":"summary_120w","lines":[{line_start},{line_end}]}}]}}

Rules:
- summary_120w: <=60 words. TERSE. State WHAT not HOW.
- inputs/outputs/side_effects/pitfalls: 1-3 word phrases MAX. [] if none.
- usage_snippet: 1-3 lines max, or "" if unclear.
- evidence: [{{"field":"summary_120w","lines":[{line_start},{line_end}]}}]
- No extra keys. Double quotes. No trailing commas.

Code:
{path} L{line_start}-{line_end}:
{snippet}

JSON:"""

    return prompt


class EnrichmentPipeline:
    """
     Orchestrates batch enrichment with clean separation of concerns.

     This pipeline replaces the monolithic qwen_enrich_batch.py script with
     a clean, testable architecture that uses the BackendAdapter protocol.

    Usage:
         from llmc.rag.enrichment_factory import create_backend_from_spec

         pipeline = EnrichmentPipeline(
             db=database,
             router=enrichment_router,
             backend_factory=create_backend_from_spec,
             prompt_builder=build_enrichment_prompt,
         )

         result = pipeline.process_batch(limit=50)
         print(f"Enriched {result.succeeded}/{result.attempted} spans")
    """

    def __init__(
        self,
        db: Database,
        router: EnrichmentRouter,
        backend_factory: BackendFactory,
        prompt_builder: Callable[[dict[str, Any]], str] | None = None,
        *,
        repo_root: Path | None = None,
        log_dir: Path | None = None,
        max_failures_per_span: int = 3,
        cooldown_seconds: int = 0,
        code_first: bool = False,
        starvation_ratio_high: int = 5,
        starvation_ratio_low: int = 1,
    ):
        self.db = db
        self.repo_root: Path = repo_root if repo_root else db.repo_root
        self.router = router
        self.backend_factory = backend_factory
        self.prompt_builder = prompt_builder or build_enrichment_prompt
        self.log_dir = log_dir
        self.max_failures = max_failures_per_span
        self.cooldown = cooldown_seconds
        self.code_first = code_first
        self.starvation_ratio_high = starvation_ratio_high
        self.starvation_ratio_low = starvation_ratio_low

        self._failure_counts: dict[str, int] = {}

    def process_batch(
        self,
        limit: int = 50,
        stop_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> EnrichmentBatchResult:
        """
        Process a batch of pending spans.

        Args:
            limit: Maximum spans to process in this batch.
            stop_check: Optional callback to check if processing should stop early.
            progress_callback: Optional callback (processed, total) for progress updates.

        Returns:
            EnrichmentBatchResult with success/failure counts and details.
        """
        start_time = time.monotonic()

        # 1. Get pending spans
        pending = self._get_pending_spans(limit)
        total_pending = len(pending)

        results: list[EnrichmentResult] = []
        succeeded = 0
        failed = 0
        skipped = 0

        # 2. Process each span
        for i, slice_view in enumerate(pending):
            # Check stop condition
            if stop_check and stop_check():
                break

            # Report progress
            if progress_callback:
                progress_callback(i + 1, total_pending)

            # Check failure threshold
            if self._is_failed(slice_view.span_hash):
                skipped += 1
                continue

            # Process span
            result = self._process_span(slice_view, span_number=i + 1)
            results.append(result)

            if result.success:
                succeeded += 1
            else:
                failed += 1
                self._record_failure(slice_view.span_hash)

            # Cooldown between spans
            if self.cooldown > 0:
                time.sleep(self.cooldown)

        duration = time.monotonic() - start_time

        return EnrichmentBatchResult(
            total_pending=total_pending,
            attempted=succeeded + failed,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            duration_sec=duration,
            results=results,
        )

    def _get_pending_spans(self, limit: int) -> list[EnrichmentSliceView]:
        """Get pending spans from database as EnrichmentSliceView objects."""
        # Use existing enrichment_plan helper
        from llmc.rag.workers import enrichment_plan

        # Fetch more items than limit if prioritizing, to have a pool to sort from.
        # Use 10x multiplier to ensure diversity (database uses RANDOM() sampling).
        fetch_limit = limit * 10 if self.code_first else limit

        items = enrichment_plan(
            self.db, self.repo_root, limit=fetch_limit, cooldown_seconds=self.cooldown
        )

        # Apply code-first prioritization if enabled
        if self.code_first and items:
            try:
                from llmc.core import load_config as _load_llmc_config
                from llmc.enrichment import FileClassifier, load_path_weight_map

                cfg = _load_llmc_config(self.repo_root)
                weight_map = load_path_weight_map(cfg)
                classifier = FileClassifier(
                    repo_root=self.repo_root, weight_config=weight_map
                )

                # Classify all items
                decisions = []

                # Helper wrapper to satisfy FileClassifier interface
                @dataclass
                class ItemWrapper:
                    file_path: str
                    slice_type: str

                for item in items:
                    wrapper = ItemWrapper(
                        file_path=item["path"],
                        slice_type=item.get("content_type", "code"),
                    )
                    decision = classifier.classify_span(wrapper)
                    decisions.append((item, decision))

                # Bucketing
                high_items = []
                mid_items = []
                low_items = []

                for item, decision in decisions:
                    if decision.weight <= 3:
                        high_items.append((item, decision))
                    elif decision.weight <= 6:
                        mid_items.append((item, decision))
                    else:
                        low_items.append((item, decision))

                def key(pair):
                    return pair[1].final_priority

                high_items.sort(key=key, reverse=True)
                mid_items.sort(key=key, reverse=True)
                low_items.sort(key=key, reverse=True)

                # Scheduling
                high_pool = high_items + mid_items
                scheduled = []

                high_ratio = self.starvation_ratio_high
                low_ratio = self.starvation_ratio_low

                while high_pool or low_items:
                    # Drain high pool
                    for _ in range(high_ratio):
                        if not high_pool:
                            break
                        scheduled.append(high_pool.pop(0)[0])
                        if len(scheduled) >= limit:
                            break
                    if len(scheduled) >= limit:
                        break

                    # Drain low pool
                    if low_items and low_ratio > 0:
                        scheduled.append(low_items.pop(0)[0])
                        if len(scheduled) >= limit:
                            break

                    if not high_pool and not low_items:
                        break

                items = scheduled

            except ImportError:
                # Fallback if llmc package not available
                pass
            except Exception as e:
                print(f"  ⚠️  Prioritization failed: {e}", file=sys.stderr)
                # Fallback to original order

        # Truncate to original limit if we fetched more
        items = items[:limit]

        views = []
        for item in items:
            # Extract data from enrichment plan item
            file_path = item.get("path", "")
            lines = item.get("lines", [0, 0])

            view = EnrichmentSliceView(
                span_hash=item["span_hash"],
                file_path=Path(file_path),
                start_line=lines[0] if len(lines) > 0 else 0,
                end_line=lines[1] if len(lines) > 1 else 0,
                content_type=item.get("content_type", "code"),
                classifier_confidence=item.get("confidence", 0.8),
                approx_token_count=item.get("approx_tokens", 500),
            )
            views.append(view)

        return views

    def _process_span(
        self, slice_view: EnrichmentSliceView, span_number: int = 0
    ) -> EnrichmentResult:
        """Process a single span through the pipeline."""
        start_time = time.monotonic()

        # 1. Route to get chain decision
        decision = self.router.choose_chain(slice_view)

        # 2. Build cascade from backend specs
        backends = [self.backend_factory(spec) for spec in decision.backend_specs]
        cascade = BackendCascade(backends=backends)

        # 3. Build prompt
        item = self._slice_to_item(slice_view)
        prompt = self.prompt_builder(item)

        # 4. Execute cascade
        try:
            result, meta, attempts = cascade.generate_for_span(prompt, item=item)

            # 5. Write to database (and graph edges for tech docs)
            self._write_enrichment(
                slice_view.span_hash, result, meta, slice_view=slice_view
            )

            duration = time.monotonic() - start_time

            # 6. Log detailed enrichment info (restored from qwen_enrich_batch.py)
            self._log_enrichment_success(
                span_number=span_number,
                file_path=slice_view.file_path,
                start_line=slice_view.start_line,
                end_line=slice_view.end_line,
                duration=duration,
                meta=meta,
                decision=decision,
                attempts=attempts,
            )

            return EnrichmentResult(
                span_hash=slice_view.span_hash,
                success=True,
                enrichment=result,
                attempts=attempts,
                route_decision=decision,
                duration_sec=duration,
            )

        except BackendError as e:
            duration = time.monotonic() - start_time

            # Log failure details
            self._log_enrichment_failure(
                span_number=span_number,
                file_path=slice_view.file_path,
                start_line=slice_view.start_line,
                end_line=slice_view.end_line,
                duration=duration,
                error=str(e),
                attempts=getattr(e, "attempts", []),
            )

            return EnrichmentResult(
                span_hash=slice_view.span_hash,
                success=False,
                enrichment=None,
                attempts=getattr(e, "attempts", []),
                route_decision=decision,
                duration_sec=duration,
                error=str(e),
            )

    def _slice_to_item(self, slice_view: EnrichmentSliceView) -> dict[str, Any]:
        """Convert slice view to item dict for prompt building."""
        # Fetch actual content from database
        try:
            span = self.db.get_span_by_hash(slice_view.span_hash)
        except Exception:
            span = None

        # Read source content from file
        code_snippet = ""
        if span:
            try:
                code_snippet = span.read_source(self.repo_root)
            except Exception as e:
                print(
                    f"  ⚠️  Could not read source for {slice_view.span_hash}: {e}",
                    file=sys.stderr,
                )

        return {
            "span_hash": slice_view.span_hash,
            "path": str(slice_view.file_path),
            "file_path": str(slice_view.file_path),
            "lines": [slice_view.start_line, slice_view.end_line],
            "line_range": [slice_view.start_line, slice_view.end_line],
            "content": code_snippet,
            "code_snippet": (
                code_snippet[:800] if code_snippet else ""
            ),  # Truncate for prompt
            "symbol": span.symbol if span else "",
            "kind": span.kind if span else "",
            "content_type": slice_view.content_type,
        }

    def _write_enrichment(
        self,
        span_hash: str,
        result: dict[str, Any],
        meta: dict[str, Any],
        slice_view: EnrichmentSliceView | None = None,
    ) -> None:
        """Write enrichment result to database with performance metrics.

        For tech docs content, also writes graph edges (REFERENCES, REQUIRES, WARNS_ABOUT).
        """
        # Build the full payload with all enrichment fields
        # The result dict comes from the LLM and should have the full schema
        payload: dict[str, Any] = {
            **result,  # Include all LLM response fields
            "model": meta.get("model", "unknown"),
            "schema_version": result.get("schema_version", "enrichment.v1"),
        }

        # Store the full enrichment with performance metrics
        # meta contains tokens_per_second, eval_count, eval_duration, etc.
        self.db.store_enrichment(span_hash, payload, meta=meta)

        # CRITICAL: Commit the transaction so data is actually saved!
        # Without this, all enrichments are lost when the process ends.
        self.db.conn.commit()

        # Write tech docs graph edges if applicable
        if slice_view and self._is_tech_docs_content(slice_view, result):
            self._write_tech_docs_edges(span_hash, result, slice_view)

    def _is_tech_docs_content(
        self, slice_view: EnrichmentSliceView, result: dict[str, Any]
    ) -> bool:
        """Check if the content should be treated as tech docs for edge extraction.

        Detection heuristics:
        1. Explicit content_type of 'tech_docs' or 'docs'
        2. File extension is markdown (.md, .rst, .txt in DOCS/)
        3. Enrichment result contains tech docs fields (related_topics, prerequisites)
        """
        # Check content_type
        content_type = (
            slice_view.content_type.lower() if slice_view.content_type else ""
        )
        if content_type in ("tech_docs", "docs", "documentation"):
            return True

        # Check file extension
        file_path = str(slice_view.file_path).lower()
        tech_docs_extensions = (".md", ".markdown", ".rst", ".txt")
        if any(file_path.endswith(ext) for ext in tech_docs_extensions):
            return True

        # Check if enrichment has tech docs fields
        tech_docs_fields = (
            "related_topics",
            "prerequisites",
            "warnings",
            "key_concepts",
        )
        if any(result.get(field) for field in tech_docs_fields):
            return True

        return False

    def _write_tech_docs_edges(
        self,
        span_hash: str,
        result: dict[str, Any],
        slice_view: EnrichmentSliceView,
    ) -> None:
        """Write graph edges from tech docs enrichment.

        Extracts REFERENCES, REQUIRES, WARNS_ABOUT edges from enrichment fields.
        """
        try:
            from llmc.rag.schemas.tech_docs_enrichment import TechDocsEnrichment
            from llmc.rag.tech_docs_graph import write_tech_docs_edges

            # Parse enrichment result into TechDocsEnrichment schema
            # Use from_llm_response for proper validation and span_id generation
            file_path = str(slice_view.file_path)
            section_path = result.get("section_path", "")

            enrichment = TechDocsEnrichment.from_llm_response(
                llm_output=result,
                file_path=file_path,
                section_path=section_path,
            )

            # Write edges to database
            edge_result = write_tech_docs_edges(
                db=self.db,
                span_hash=span_hash,
                enrichment=enrichment,
                source_file_path=file_path,
            )

            if edge_result.edges_created > 0:
                print(
                    f"  📊 Created {edge_result.edges_created} graph edges "
                    f"({edge_result.edges_unresolved} unresolved)",
                    flush=True,
                )

        except ImportError:
            # Tech docs graph module not available - skip silently
            pass
        except Exception as e:
            # Log but don't fail enrichment for edge creation errors
            print(f"  ⚠️  Edge creation failed: {e}", file=sys.stderr)

    def _is_failed(self, span_hash: str) -> bool:
        """Check if span has exceeded failure threshold."""
        return self._failure_counts.get(span_hash, 0) >= self.max_failures

    def _record_failure(self, span_hash: str) -> None:
        """Increment failure count for span."""
        self._failure_counts[span_hash] = self._failure_counts.get(span_hash, 0) + 1

    def _log_enrichment_success(
        self,
        span_number: int,
        file_path: Path,
        start_line: int,
        end_line: int,
        duration: float,
        meta: dict[str, Any],
        decision: EnrichmentRouteDecision,
        attempts: list[Any],
    ) -> None:
        """Log detailed enrichment success info (restored from qwen_enrich_batch.py)."""
        # Extract metadata
        model = meta.get("model", "unknown")
        backend = meta.get("backend", "unknown")
        chain_name = decision.chain_name or "default"

        # Build model note
        model_note = f" ({model})" if model and model != "unknown" else ""

        # Build backend/chain note
        config_parts = []
        if chain_name and chain_name != "default":
            config_parts.append(f"chain={chain_name}")
        if backend and backend != "unknown":
            config_parts.append(f"backend={backend}")

        # Add host/URL if available
        host = meta.get("host") or meta.get("host_url") or meta.get("base_url")
        if host:
            config_parts.append(f"url={host}")

        config_note = f" [{', '.join(config_parts)}]" if config_parts else ""

        # Build attempts note
        attempt_count = len(attempts)
        attempts_note = (
            f" [{attempt_count} attempt{'s' if attempt_count != 1 else ''}]"
            if attempt_count > 1
            else ""
        )

        # Build T/s note (tokens per second)
        tps = meta.get("tokens_per_second", 0)
        tps_note = f" {tps:.1f} T/s" if tps and tps > 0 else ""

        # Print detailed log line (matching old format)
        print(
            f"✓ Enriched span {span_number}: {file_path}:{start_line}-{end_line} "
            f"({duration:.2f}s){tps_note}{model_note}{config_note}{attempts_note}",
            flush=True,
        )

    def _log_enrichment_failure(
        self,
        span_number: int,
        file_path: Path,
        start_line: int,
        end_line: int,
        duration: float,
        error: str,
        attempts: list[Any],
    ) -> None:
        """Log detailed enrichment failure info."""
        attempt_count = len(attempts)
        attempts_note = (
            f" [{attempt_count} attempt{'s' if attempt_count != 1 else ''}]"
            if attempts
            else ""
        )

        # Truncate error message if too long
        error_msg = error[:100] + "..." if len(error) > 100 else error

        print(
            f"✗ Failed span {span_number}: {file_path}:{start_line}-{end_line} "
            f"({duration:.2f}s){attempts_note} - {error_msg}",
            file=sys.stderr,
            flush=True,
        )
