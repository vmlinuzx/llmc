# SDD: Enrichment Pipeline Tidy-Up (Roadmap 1.2)

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Ready to Implement  
**Effort:** 4-6 hours  
**Difficulty:** 🟡 Medium

---

## Executive Summary

The enrichment system has good abstractions (`BackendAdapter`, `BackendCascade`, `EnrichmentRouter`) but the actual orchestration is buried in a 2,271-line script (`qwen_enrich_batch.py`). This SDD extracts a clean `EnrichmentPipeline` module that wires: pending spans → router → backend cascade → DB writes.

---

## 1. Current State

### What's Good (Keep As-Is)

| Module | Purpose | Status |
|--------|---------|--------|
| `enrichment_backends.py` | `BackendAdapter` protocol, `BackendCascade`, `AttemptRecord` | ✅ Clean, well-typed |
| `enrichment_router.py` | `EnrichmentRouter`, `EnrichmentSliceView`, `EnrichmentRouteDecision` | ✅ Clean, well-typed |
| `config_enrichment.py` | `EnrichmentConfig`, `EnrichmentBackendSpec`, config loading | ✅ Clean, well-typed |
| `enrichment_db_helpers.py` | DB read/write for enrichments | ✅ Works |

### What's Messy

| Module | Problem |
|--------|---------|
| `qwen_enrich_batch.py` (2,271 lines) | Everything: LLM calls, host probing, batch loops, metrics, GPU monitoring, prompt building, JSON parsing, retry logic |
| `enrichment.py` | Mixed concerns: query-time enrichment (HybridRetriever) + batch orchestration (enrich_spans) |
| `runner.py` | Shells out to `qwen_enrich_batch.py` subprocess |
| `service.py` | Calls `runner.run_enrich()` which shells out |

### The Gap

There's no clean abstraction for:
```
pending_spans → choose_chain() → BackendCascade.generate_for_span() → write_enrichment()
```

Instead it's all interleaved in a giant script with subprocess calls.

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      EnrichmentPipeline                         │
│                                                                 │
│   __init__(config, router, backend_factory, db)                 │
│                                                                 │
│   process_batch(limit=50) → EnrichmentBatchResult               │
│       │                                                         │
│       ├─▶ 1. pending_enrichments(db, limit)                     │
│       │       └─▶ list[EnrichmentSliceView]                     │
│       │                                                         │
│       ├─▶ 2. For each slice:                                    │
│       │       ├─▶ router.choose_chain(slice)                    │
│       │       │       └─▶ EnrichmentRouteDecision               │
│       │       │                                                 │
│       │       ├─▶ backend_factory(decision.backend_specs)       │
│       │       │       └─▶ BackendCascade                        │
│       │       │                                                 │
│       │       ├─▶ cascade.generate_for_span(prompt, item)       │
│       │       │       └─▶ (result, meta, attempts)              │
│       │       │                                                 │
│       │       └─▶ write_enrichment(db, span_hash, result)       │
│       │                                                         │
│       └─▶ 3. Return EnrichmentBatchResult                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementation Plan

### Phase 1: Extract OllamaBackend (1-2 hours)

Create a proper `BackendAdapter` implementation for Ollama.

**New file:** `tools/rag/enrichment_adapters/ollama.py`

```python
"""Ollama backend adapter for enrichment."""

from dataclasses import dataclass
from typing import Any
import httpx

from tools.rag.enrichment_backends import BackendAdapter, BackendError
from tools.rag.config_enrichment import EnrichmentBackendSpec


@dataclass
class OllamaBackend:
    """BackendAdapter implementation for Ollama."""
    
    spec: EnrichmentBackendSpec
    client: httpx.Client
    
    @classmethod
    def from_spec(cls, spec: EnrichmentBackendSpec) -> "OllamaBackend":
        timeout = spec.timeout_seconds or 120
        client = httpx.Client(
            base_url=spec.url or "http://localhost:11434",
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        return cls(spec=spec, client=client)
    
    @property
    def config(self) -> EnrichmentBackendSpec:
        return self.spec
    
    def describe_host(self) -> str | None:
        return self.spec.url
    
    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate enrichment via Ollama API."""
        payload = {
            "model": self.spec.model,
            "prompt": prompt,
            "stream": False,
            "options": self.spec.options or {},
        }
        
        try:
            response = self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as e:
            raise BackendError(
                f"Ollama timeout after {self.spec.timeout_seconds}s",
                failure_type="timeout",
            ) from e
        except httpx.HTTPStatusError as e:
            raise BackendError(
                f"Ollama HTTP error: {e.response.status_code}",
                failure_type="http_error",
            ) from e
        except Exception as e:
            raise BackendError(
                f"Ollama error: {e}",
                failure_type="backend_error",
            ) from e
        
        # Parse response
        raw_text = data.get("response", "")
        result = self._parse_enrichment(raw_text, item)
        
        meta = {
            "model": data.get("model"),
            "host": self.spec.url,
            "eval_count": data.get("eval_count"),
            "eval_duration": data.get("eval_duration"),
        }
        
        return result, meta
    
    def _parse_enrichment(self, text: str, item: dict) -> dict[str, Any]:
        """Parse LLM output into enrichment fields."""
        # Extract JSON from response (handle markdown fences)
        import json
        import re
        
        # Try to find JSON in response
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback: return raw as summary
        return {
            "summary": text.strip()[:500],
            "key_topics": [],
            "complexity": "unknown",
        }
```

### Phase 2: Create EnrichmentPipeline (2-3 hours)

The core orchestrator that ties everything together.

**New file:** `tools/rag/enrichment_pipeline.py`

```python
"""
Enrichment Pipeline - Clean orchestration for batch enrichment.

This module provides the EnrichmentPipeline class which coordinates:
- Span selection (pending enrichments from DB)
- Chain selection (via EnrichmentRouter)
- Backend execution (via BackendCascade)
- Result persistence (DB writes)
- Metrics/logging (JSONL events)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from tools.rag.database import Database
from tools.rag.enrichment_backends import (
    AttemptRecord,
    BackendAdapter,
    BackendCascade,
    BackendError,
)
from tools.rag.enrichment_router import (
    EnrichmentRouter,
    EnrichmentRouteDecision,
    EnrichmentSliceView,
)
from tools.rag.config_enrichment import EnrichmentBackendSpec


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


class EnrichmentPipeline:
    """
    Orchestrates batch enrichment with clean separation of concerns.
    
    Usage:
        pipeline = EnrichmentPipeline(
            db=database,
            router=enrichment_router,
            backend_factory=OllamaBackend.from_spec,
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
        prompt_builder: Callable[[dict[str, Any]], str],
        *,
        log_dir: Path | None = None,
        max_failures_per_span: int = 3,
        cooldown_seconds: int = 0,
    ):
        self.db = db
        self.router = router
        self.backend_factory = backend_factory
        self.prompt_builder = prompt_builder
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
        # Use existing pending_enrichments helper
        from tools.rag.workers import enrichment_plan
        
        items = enrichment_plan(self.db, self.db.repo_root, limit=limit)
        
        views = []
        for item in items:
            view = EnrichmentSliceView(
                span_hash=item["span_hash"],
                file_path=Path(item.get("file_path", "")),
                start_line=item.get("start_line", 0),
                end_line=item.get("end_line", 0),
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
                attempts=e.attempts or [],
                route_decision=decision,
                duration_sec=duration,
                error=str(e),
            )
    
    def _slice_to_item(self, slice_view: EnrichmentSliceView) -> dict[str, Any]:
        """Convert slice view to item dict for prompt building."""
        # Fetch actual content from database
        span = self.db.get_span_by_hash(slice_view.span_hash)
        
        return {
            "span_hash": slice_view.span_hash,
            "file_path": str(slice_view.file_path),
            "start_line": slice_view.start_line,
            "end_line": slice_view.end_line,
            "content": span.content if span else "",
            "symbol": span.symbol if span else "",
            "kind": span.kind if span else "",
        }
    
    def _write_enrichment(
        self,
        span_hash: str,
        result: dict[str, Any],
        meta: dict[str, Any],
    ) -> None:
        """Write enrichment result to database."""
        from tools.rag.enrichment_db_helpers import write_enrichment
        
        write_enrichment(
            self.db,
            span_hash=span_hash,
            summary=result.get("summary", ""),
            key_topics=result.get("key_topics", []),
            complexity=result.get("complexity", "unknown"),
            model=meta.get("model", "unknown"),
        )
    
    def _is_failed(self, span_hash: str) -> bool:
        """Check if span has exceeded failure threshold."""
        return self._failure_counts.get(span_hash, 0) >= self.max_failures
    
    def _record_failure(self, span_hash: str) -> None:
        """Increment failure count for span."""
        self._failure_counts[span_hash] = self._failure_counts.get(span_hash, 0) + 1
```

### Phase 3: Wire Into Service (1-2 hours)

Update `service.py` to use the pipeline instead of shelling out.

**Changes to `tools/rag/service.py`:**

```python
# In RAGService.process_repo():

def process_repo(self, repo_path: str) -> bool:
    """Process one repo. Returns True if work was done."""
    repo = Path(repo_path)
    work_done = False
    
    # ... existing sync logic ...
    
    # Step 2: Enrich via pipeline (replaces subprocess call)
    try:
        from tools.rag.enrichment_pipeline import EnrichmentPipeline
        from tools.rag.enrichment_adapters.ollama import OllamaBackend
        from tools.rag.enrichment_router import build_router_from_toml
        from tools.rag.prompts import build_enrichment_prompt
        
        router = build_router_from_toml(repo)
        db = Database(index_path_for_write(repo))
        
        pipeline = EnrichmentPipeline(
            db=db,
            router=router,
            backend_factory=OllamaBackend.from_spec,
            prompt_builder=build_enrichment_prompt,
            max_failures_per_span=self.max_failures,
        )
        
        batch_size = self._toml_cfg.get("enrichment", {}).get("batch_size", 50)
        result = pipeline.process_batch(limit=batch_size)
        
        if result.attempted > 0:
            work_done = True
            print(f"  ✅ Enriched {result.succeeded}/{result.attempted} spans")
        else:
            print(f"  ℹ️  No pending enrichments")
            
    except Exception as e:
        print(f"  ⚠️  Enrichment failed: {e}")
    
    # ... rest of processing ...
    return work_done
```

---

## 4. File Structure After Implementation

```
tools/rag/
├── enrichment_backends.py      # Existing (unchanged)
│   ├── BackendAdapter (Protocol)
│   ├── BackendCascade
│   ├── AttemptRecord
│   └── BackendError
│
├── enrichment_adapters/        # NEW
│   ├── __init__.py
│   ├── ollama.py               # OllamaBackend implementation
│   └── base.py                 # Shared utilities
│
├── enrichment_pipeline.py      # NEW - Core orchestrator
│   ├── EnrichmentPipeline
│   ├── EnrichmentResult
│   └── EnrichmentBatchResult
│
├── enrichment_router.py        # Existing (unchanged)
├── config_enrichment.py        # Existing (unchanged)
├── enrichment_db_helpers.py    # Existing (unchanged)
│
├── enrichment.py               # Existing - query-time only
│   ├── QueryAnalyzer           # Keep
│   ├── HybridRetriever         # Keep
│   └── enrich_spans()          # DEPRECATED → use pipeline
│
├── runner.py                   # Update run_enrich() to use pipeline
└── service.py                  # Update to use pipeline directly
```

---

## 5. Migration Strategy

### Phase 1: Add New Code (Non-Breaking)
- Add `enrichment_adapters/ollama.py`
- Add `enrichment_pipeline.py`
- Keep all existing code working

### Phase 2: Wire Service to Pipeline
- Update `service.py` to use `EnrichmentPipeline` instead of subprocess
- Keep `qwen_enrich_batch.py` as fallback (env flag)

### Phase 3: Deprecation (Later)
- Mark `qwen_enrich_batch.py` as deprecated
- Mark `enrichment.py:enrich_spans()` as deprecated
- Eventually remove after validation period

---

## 6. Benefits

| Before | After |
|--------|-------|
| 2,271-line script with everything | Clean 200-line pipeline module |
| Subprocess calls between Python | Direct function calls |
| Implicit contracts | Explicit `BackendAdapter` protocol |
| Mixed concerns in `enrichment.py` | Query-time vs batch-time separated |
| Hard to test | Easy to mock `BackendFactory` |
| No type hints in critical paths | Full typing throughout |

---

## 7. Testing Strategy

### Unit Tests
```python
def test_pipeline_processes_batch():
    """Pipeline processes pending spans through cascade."""
    mock_db = MockDatabase(pending_spans=[...])
    mock_router = MockRouter(chain="test-chain")
    mock_factory = lambda spec: MockBackend(returns={"summary": "test"})
    
    pipeline = EnrichmentPipeline(
        db=mock_db,
        router=mock_router,
        backend_factory=mock_factory,
        prompt_builder=lambda x: "test prompt",
    )
    
    result = pipeline.process_batch(limit=10)
    
    assert result.succeeded == 10
    assert mock_db.write_calls == 10

def test_pipeline_handles_cascade_failure():
    """Pipeline records failure when all backends fail."""
    mock_factory = lambda spec: MockBackend(raises=BackendError("fail"))
    
    pipeline = EnrichmentPipeline(...)
    result = pipeline.process_batch(limit=1)
    
    assert result.failed == 1
    assert result.results[0].error == "fail"

def test_pipeline_skips_failed_spans():
    """Pipeline skips spans that exceeded failure threshold."""
    pipeline = EnrichmentPipeline(max_failures_per_span=2)
    pipeline._failure_counts["span123"] = 2
    
    # span123 should be skipped
    result = pipeline.process_batch(limit=10)
    assert result.skipped >= 1
```

### Integration Test
```python
def test_ollama_backend_live():
    """OllamaBackend calls real Ollama (skip if not available)."""
    pytest.importorskip("httpx")
    
    spec = EnrichmentBackendSpec(
        name="test",
        provider="ollama",
        model="qwen2.5:7b",
        url="http://localhost:11434",
    )
    
    backend = OllamaBackend.from_spec(spec)
    result, meta = backend.generate("Summarize: hello world", item={})
    
    assert "summary" in result or "response" in meta
```

---

## 8. Decision: Create `enrichment_pipeline` Module?

**Answer: YES**

The roadmap asked whether to create a dedicated pipeline module. Based on analysis:

1. **Separation of concerns:** Query-time enrichment (HybridRetriever) is fundamentally different from batch enrichment
2. **Testability:** A clean pipeline class is much easier to unit test than a 2,271-line script
3. **Future extensibility:** Remote providers (Gemini, OpenAI) plug in via `BackendFactory`
4. **No breaking changes:** Existing code continues to work during migration

---

## 9. Summary

| Phase | Effort | Deliverables |
|-------|--------|--------------|
| Extract OllamaBackend | 1-2h | `enrichment_adapters/ollama.py` |
| Create EnrichmentPipeline | 2-3h | `enrichment_pipeline.py` |
| Wire into Service | 1-2h | Update `service.py` |
| **Total** | **4-6h** | Clean, testable pipeline |

This sets the foundation for Roadmap 3.6 (Remote LLM Providers) - new backends just implement `BackendAdapter` and get passed to the same pipeline.
