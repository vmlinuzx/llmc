"""
Enrichment Pipeline - Clean orchestration for batch enrichment.

This module provides the EnrichmentPipeline class which coordinates:
- Span selection (pending enrichments from DB)
- Chain selection (via EnrichmentRouter)
- Backend execution (via BackendCascade)
- Result persistence (DB writes)
- Metrics/logging (JSONL events)

Usage:
    from tools.rag.enrichment_pipeline import EnrichmentPipeline
    from tools.rag.enrichment_factory import create_backend_from_spec
    
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

from tools.rag.config_enrichment import EnrichmentBackendSpec
from tools.rag.database import Database
from tools.rag.enrichment_backends import (
    AttemptRecord,
    BackendAdapter,
    BackendCascade,
    BackendError,
)
from tools.rag.enrichment_router import (
    EnrichmentRouteDecision,
    EnrichmentRouter,
    EnrichmentSliceView,
)


class BackendFactory(Protocol):
    """Factory protocol for creating backend adapters from specs."""
    
    def __call__(self, spec: EnrichmentBackendSpec) -> BackendAdapter:
        ...


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


def build_enrichment_prompt(item: dict[str, Any]) -> str:
    """Build enrichment prompt from span item.
    
    This is adapted from qwen_enrich_batch.py's build_prompt function.
    
    Args:
        item: Span data dict with path, lines, code_snippet, etc.
        
    Returns:
        Formatted prompt string ready for LLM
    """
    path = item.get("path", item.get("file_path", ""))
    line_start, line_end = item.get("lines", item.get("line_range", [0, 0]))
    snippet = item.get("code_snippet", item.get("content", ""))
    
    # Ensure we have valid line numbers
    if not isinstance(line_start, int) or not isinstance(line_end, int):
        line_start, line_end = 0, 0
    
    prompt = f"""Return ONLY ONE VALID JSON OBJECT in ENGLISH.
No markdown, no comments, no extra text.

Output example (structure and keys are FIXED):
{{"summary_120w":"...","inputs":["..."],"outputs":["..."],
"side_effects":["..."],"pitfalls":["..."],
"usage_snippet":"...","evidence":[{{"field":"summary_120w","lines":[{line_start},{line_end}]}}]}}

Rules:
- summary_120w: <=120 English words describing what the code does.
- inputs/outputs/side_effects/pitfalls: lists of short phrases; use [] if none.
- usage_snippet: 1–5 line usage example, or "" if unclear.
- evidence: list of objects:
  - "field" is one of:
    "summary_120w","inputs","outputs","side_effects","pitfalls","usage_snippet"
  - "lines" MUST be [{line_start},{line_end}] for every entry.
- Do NOT add or rename keys.
- Use double quotes, no trailing commas.

Code to analyze:
{path} L{line_start}-{line_end}:
{snippet}

JSON RESPONSE LATIN-1 CHARACTERS ONLY:"""
    
    return prompt


class EnrichmentPipeline:
    """
    Orchestrates batch enrichment with clean separation of concerns.
    
    This pipeline replaces the monolithic qwen_enrich_batch.py script with
    a clean, testable architecture that uses the BackendAdapter protocol.
   
   Usage:
        from tools.rag.enrichment_factory import create_backend_from_spec
        
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
    ):
        self.db = db
        self.repo_root: Path = repo_root if repo_root else db.repo_root
        self.router = router
        self.backend_factory = backend_factory
        self.prompt_builder = prompt_builder or build_enrichment_prompt
        self.log_dir = log_dir
        self.max_failures = max_failures_per_span
        self.cooldown = cooldown_seconds
        
        self._failure_counts: dict[str, int] = {}
    
    def process_batch(self, limit: int = 50) -> EnrichmentBatchResult:
        """
        Process a batch of pending spans.
        
        Args:
            limit: Maximum spans to process in this batch.
        
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
        for slice_view in pending:
            # Check failure threshold
            if self._is_failed(slice_view.span_hash):
                skipped += 1
                continue
            
            # Process span
            result = self._process_span(slice_view)
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
        from tools.rag.workers import enrichment_plan
        
        items = enrichment_plan(
            self.db,
            self.repo_root,
            limit=limit,
            cooldown_seconds=self.cooldown
        )
        
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
    
    def _process_span(self, slice_view: EnrichmentSliceView) -> EnrichmentResult:
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
            
            # 5. Write to database
            self._write_enrichment(slice_view.span_hash, result, meta)
            
            duration = time.monotonic() - start_time
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
            return EnrichmentResult(
                span_hash=slice_view.span_hash,
                success=False,
                enrichment=None,
                attempts=getattr(e, 'attempts', []),
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
                print(f"  ⚠️  Could not read source for {slice_view.span_hash}: {e}", file=sys.stderr)
        
        return {
            "span_hash": slice_view.span_hash,
            "path": str(slice_view.file_path),
            "file_path": str(slice_view.file_path),
            "lines": [slice_view.start_line, slice_view.end_line],
            "line_range": [slice_view.start_line, slice_view.end_line],
            "content": code_snippet,
            "code_snippet": code_snippet[:800] if code_snippet else "",  # Truncate for prompt
            "symbol": span.symbol if span else "",
            "kind": span.kind if span else "",
            "content_type": slice_view.content_type,
        }
    
    def _write_enrichment(
        self,
        span_hash: str,
        result: dict[str, Any],
        meta: dict[str, Any],
    ) -> None:
        """Write enrichment result to database."""
        from tools.rag.enrichment_db_helpers import write_enrichment
        
        # Extract fields from result
        summary = result.get("summary", result.get("summary_120w", ""))
        key_topics = result.get("key_topics", result.get("inputs", []))
        complexity = result.get("complexity", "unknown")
        model = meta.get("model", "unknown")
        
        write_enrichment(
            self.db,
            span_hash=span_hash,
            summary=summary,
            key_topics=key_topics,
            complexity=complexity,
            model=model,
        )
    
    def _is_failed(self, span_hash: str) -> bool:
        """Check if span has exceeded failure threshold."""
        return self._failure_counts.get(span_hash, 0) >= self.max_failures
    
    def _record_failure(self, span_hash: str) -> None:
        """Increment failure count for span."""
        self._failure_counts[span_hash] = self._failure_counts.get(span_hash, 0) + 1
