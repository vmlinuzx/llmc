"""
Pool Worker - Backend-bound enrichment worker process.

This worker is bound to a specific Ollama backend and pulls work from the
central enrichment queue. Unlike the EnrichmentWorker which uses the router
to select a chain, this worker calls its assigned backend directly.

This enables true multi-server parallelization:
- Each worker is bound to ONE Ollama backend
- All workers pull from the SAME central queue
- Fast servers naturally get more work (work-stealing pattern)

Usage:
    LLMC_WORKER_ID=athena \
    LLMC_WORKER_HOST=athena \
    LLMC_WORKER_PORT=11434 \
    LLMC_WORKER_MODEL=qwen3:4b-instruct \
    python3 -m llmc.rag.pool_worker

Environment Variables:
    LLMC_WORKER_ID:     Unique identifier for this worker (e.g., "athena", "desktop")
    LLMC_WORKER_HOST:   Ollama server hostname or IP
    LLMC_WORKER_PORT:   Ollama server port (default: 11434)
    LLMC_WORKER_MODEL:  Model to use for enrichment (e.g., "qwen3:4b-instruct")
    LLMC_QUEUE_DB:      Optional path to work queue database

See Also:
    - SDD_Event_Driven_Enrichment_Queue.md
    - HLD_Multi_Server_Enrichment_Pool.md
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any

import requests

from llmc.rag.config import index_path_for_write
from llmc.rag.database import Database
from llmc.rag.enrichment_pipeline import build_enrichment_prompt
from llmc.rag.enrichment_router import EnrichmentSliceView
from llmc.rag.work_queue import WorkItem, get_queue

log = logging.getLogger(__name__)


@dataclass
class PoolWorkerStats:
    """Statistics for a pool worker session."""

    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    total_duration_sec: float = 0.0
    total_tokens: int = 0


@dataclass
class SpanInfo:
    """Span details for logging."""

    symbol: str
    start_line: int
    end_line: int

    def __str__(self) -> str:
        """Format as 'symbol L<start>-<end>' for log output."""
        if self.symbol:
            return f"{self.symbol} L{self.start_line}-{self.end_line}"
        return f"L{self.start_line}-{self.end_line}"


@dataclass
class EnrichmentMeta:
    """Metadata from an Ollama enrichment call."""

    model: str
    backend: str
    host_url: str
    eval_count: int = 0
    eval_duration_ns: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration_ns: int = 0

    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second from eval metrics."""
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count / (self.eval_duration_ns / 1e9)


class PoolWorker:
    """
    Worker bound to a specific Ollama backend.

    Unlike EnrichmentWorker which uses the router to select a chain,
    this worker calls its assigned Ollama backend directly. This enables
    true multi-server parallelization where each worker processes work
    independently.

    Key differences from EnrichmentWorker:
    - Backend is fixed at startup (from environment variables)
    - Calls Ollama directly (bypasses router)
    - Logging includes worker ID and backend info
    """

    def __init__(self):
        """Initialize worker from environment variables."""
        # Required environment variables
        self.worker_id = os.environ.get("LLMC_WORKER_ID")
        self.ollama_host = os.environ.get("LLMC_WORKER_HOST")
        self.ollama_port = int(os.environ.get("LLMC_WORKER_PORT", "11434"))
        self.model = os.environ.get("LLMC_WORKER_MODEL")

        if not all([self.worker_id, self.ollama_host, self.model]):
            raise ValueError(
                "Missing required environment variables. Required: "
                "LLMC_WORKER_ID, LLMC_WORKER_HOST, LLMC_WORKER_MODEL"
            )

        # Optional: custom queue database path
        queue_db_path = os.environ.get("LLMC_QUEUE_DB")
        self.queue = get_queue(Path(queue_db_path) if queue_db_path else None)

        self.ollama_url = f"http://{self.ollama_host}:{self.ollama_port}"
        self.stats = PoolWorkerStats()
        self.running = True

        # Configurable timeout (from env or default)
        self.request_timeout = int(os.environ.get("LLMC_WORKER_TIMEOUT", "120"))
        
        # Configurable Ollama options (from env as JSON or defaults)
        options_json = os.environ.get("LLMC_WORKER_OPTIONS", "{}")
        try:
            self.ollama_options = json.loads(options_json) if options_json else {}
        except json.JSONDecodeError:
            self.ollama_options = {}

        # Tiered processing configuration
        self.tier = int(os.environ.get("LLMC_WORKER_TIER", "0"))
        self.max_tier = int(os.environ.get("LLMC_MAX_TIER", "2"))
        
        # Apply sensible defaults if not specified
        if "temperature" not in self.ollama_options:
            self.ollama_options["temperature"] = 0.1  # Low for consistent output
        if "num_predict" not in self.ollama_options:
            self.ollama_options["num_predict"] = 1024  # Max tokens

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM by setting running to False for graceful drain."""
        print(f"[{self.worker_id}] Received SIGTERM. Draining...", flush=True)
        self.running = False

    def run(self):
        """Main worker loop - pull work, process, repeat."""
        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        print(
            f"[{self.worker_id}] Started (tier={self.tier}), using {self.ollama_url} with {self.model}",
            flush=True,
        )

        # Health check on startup
        if not self._health_check():
            print(
                f"[{self.worker_id}] ❌ Failed initial health check for {self.ollama_url}",
                flush=True,
            )
            print(f"[{self.worker_id}] Will retry on first work item...", flush=True)

        while self.running:
            # Wait for work notification (with timeout for polling fallback)
            try:
                self.queue.wait_for_work(timeout=5.0)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"[{self.worker_id}] Error waiting for work: {e}")
                time.sleep(1)
                continue

            # Pull work from central queue
            try:
                items = self.queue.pull_work(self.worker_id, tier=self.tier, limit=1)
            except Exception as e:
                log.error(f"[{self.worker_id}] Error pulling work: {e}")
                time.sleep(1)
                continue

            if not items:
                # No work available, loop back to wait
                continue

            item = items[0]
            start_time = time.time()

            # Check max attempts - if exceeded, mark as permanently failed
            max_attempts = int(os.environ.get("LLMC_WORKER_MAX_ATTEMPTS", "3"))
            if item.attempts >= max_attempts:
                self.queue.complete_work(item.id, self.worker_id)
                print(
                    f"[{self.worker_id}] ⏭️ {item.file_path}: max attempts ({item.attempts}) exceeded, skipping",
                    flush=True,
                )
                self.stats.items_processed += 1
                continue

            # Skip items for repos that no longer exist (orphaned queue items)
            repo_path = Path(item.repo_path)
            if not repo_path.exists():
                self.queue.complete_work(item.id, self.worker_id)
                print(
                    f"[{self.worker_id}] 🗑️ {item.file_path}: repo gone, removing from queue",
                    flush=True,
                )
                self.stats.items_processed += 1
                continue

            try:
                meta, span_info = self._process_item(item)
                duration = time.time() - start_time

                self.queue.complete_work(item.id, self.worker_id)
                self.stats.items_succeeded += 1
                self.stats.total_duration_sec += duration
                self.stats.total_tokens += meta.eval_count if meta else 0

                tps = meta.tokens_per_second if meta else 0
                span_str = str(span_info) if span_info else item.span_hash[:8]
                print(
                    f"[{self.worker_id}] ✅ {item.file_path} [{span_str}] (tier={self.tier}, {duration:.2f}s, {tps:.1f} T/s)",
                    flush=True,
                )

            except (FileNotFoundError, PermissionError) as e:
                # File/span deleted OR malformed repo path - just complete and move on
                self.queue.complete_work(item.id, self.worker_id)
                print(
                    f"[{self.worker_id}] 🗑️ {item.file_path}: {type(e).__name__}, removing from queue",
                    flush=True,
                )

            except Exception as e:
                duration = time.time() - start_time
                attempts_per_tier = 3
                self.queue.fail_work(
                    item.id, str(e), self.worker_id, 
                    max_tier=self.max_tier,
                    attempts_per_tier=attempts_per_tier
                )
                self.stats.items_failed += 1

                # Truncate error for log (keep first 80 chars)
                err_msg = str(e)[:80].replace('\n', ' ')
                span_id = item.span_hash[:16]  # Longer hash for debugging failures
                attempt_num = item.attempts + 1  # 1-indexed for display
                
                # Determine what happens next based on attempt count
                if attempt_num >= attempts_per_tier:
                    if item.escalation_tier >= self.max_tier:
                        print(
                            f"[{self.worker_id}] ❌ {item.file_path} [{span_id}]: PERMANENTLY FAILED after {attempts_per_tier} tries at tier {self.tier} ({err_msg})",
                            flush=True,
                        )
                    else:
                        print(
                            f"[{self.worker_id}] ⬆️ {item.file_path} [{span_id}]: escalating tier {item.escalation_tier}→{item.escalation_tier + 1} after {attempts_per_tier} tries ({err_msg})",
                            flush=True,
                        )
                else:
                    print(
                        f"[{self.worker_id}] 🔄 {item.file_path} [{span_id}]: retry {attempt_num}/{attempts_per_tier} at tier {self.tier} ({err_msg})",
                        flush=True,
                    )

            finally:
                self.stats.items_processed += 1

        # Print final stats
        self._print_final_stats()

    def _health_check(self) -> bool:
        """Check if Ollama backend is healthy."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def _process_item(self, item: WorkItem) -> tuple[EnrichmentMeta | None, SpanInfo | None]:
        """
        Process a single work item using this worker's Ollama backend.

        This is the core difference from EnrichmentWorker: we call Ollama
        directly rather than going through the router/pipeline.

        Returns:
            Tuple of (EnrichmentMeta, SpanInfo) or (None, None) if span not found.
        """
        repo_path = Path(item.repo_path)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found: {repo_path}")

        # Open repo database
        index_path = index_path_for_write(repo_path)
        db = Database(index_path)

        try:
            span = db.get_span_by_hash(item.span_hash)
            if not span:
                # Span might have been deleted or re-indexed
                return None, None

            # Create span info for logging
            span_info = SpanInfo(
                symbol=span.symbol or "",
                start_line=span.start_line,
                end_line=span.end_line,
            )

            # Build slice view for prompt construction
            slice_view = EnrichmentSliceView(
                span_hash=item.span_hash,
                file_path=span.file_path,
                start_line=span.start_line,
                end_line=span.end_line,
                content_type=span.slice_type,
                classifier_confidence=span.classifier_confidence or 0.8,
                approx_token_count=500,  # Estimate
            )

            # Build prompt (reuse existing prompt builder)
            prompt_item = self._slice_to_item(slice_view, span, repo_path)
            prompt = build_enrichment_prompt(prompt_item, repo_path)

            # Call Ollama directly (bypass router)
            result, meta = self._call_ollama(prompt)

            # Store enrichment result
            self._store_enrichment(db, item.span_hash, result, meta)

            return meta, span_info

        finally:
            db.close()

    def _slice_to_item(
        self, slice_view: EnrichmentSliceView, span: Any, repo_root: Path
    ) -> dict[str, Any]:
        """Convert slice view to item dict for prompt building."""
        code_snippet = ""
        try:
            code_snippet = span.read_source(repo_root)
        except Exception as e:
            log.warning(f"Could not read source for {slice_view.span_hash}: {e}")

        return {
            "span_hash": slice_view.span_hash,
            "path": str(slice_view.file_path),
            "file_path": str(slice_view.file_path),
            "lines": [slice_view.start_line, slice_view.end_line],
            "line_range": [slice_view.start_line, slice_view.end_line],
            "content": code_snippet,
            "code_snippet": code_snippet[:800] if code_snippet else "",
            "symbol": span.symbol if span else "",
            "kind": span.kind if span else "",
            "content_type": slice_view.content_type,
        }

    def _call_ollama(self, prompt: str) -> tuple[dict[str, Any], EnrichmentMeta]:
        """
        Call Ollama directly on this worker's assigned backend.

        Returns:
            Tuple of (parsed_result, metadata)
        """
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": self.ollama_options,  # Configurable via LLMC_WORKER_OPTIONS
            },
            timeout=self.request_timeout,
        )
        response.raise_for_status()

        data = response.json()

        # Extract response text
        response_text = data.get("response", "")

        # Parse JSON from response (may have markdown fences)
        result = self._parse_json_response(response_text)

        # Build metadata
        meta = EnrichmentMeta(
            model=self.model,
            backend="ollama",
            host_url=self.ollama_url,
            eval_count=data.get("eval_count", 0),
            eval_duration_ns=data.get("eval_duration", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            prompt_eval_duration_ns=data.get("prompt_eval_duration", 0),
        )

        return result, meta

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown fences."""
        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Try to parse JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to find JSON object in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            raise ValueError(f"Failed to parse JSON response: {e}") from e

    def _store_enrichment(
        self, db: Database, span_hash: str, result: dict[str, Any], meta: EnrichmentMeta
    ) -> None:
        """Store enrichment result in the database."""
        payload = {
            **result,
            "model": meta.model,
            "schema_version": result.get("schema_version", "enrichment.v1"),
        }

        meta_dict = {
            "model": meta.model,
            "backend": meta.backend,
            "host_url": meta.host_url,
            "tokens_per_second": meta.tokens_per_second,
            "eval_count": meta.eval_count,
            "eval_duration": meta.eval_duration_ns,
            "prompt_eval_count": meta.prompt_eval_count,
            "prompt_eval_duration": meta.prompt_eval_duration_ns,
        }

        db.store_enrichment(span_hash, payload, meta=meta_dict)
        db.conn.commit()

    def _print_final_stats(self):
        """Print final statistics on shutdown."""
        avg_time = (
            self.stats.total_duration_sec / self.stats.items_processed
            if self.stats.items_processed > 0
            else 0
        )
        avg_tps = (
            self.stats.total_tokens / self.stats.total_duration_sec
            if self.stats.total_duration_sec > 0
            else 0
        )

        print(f"\n[{self.worker_id}] === Final Statistics ===", flush=True)
        print(f"[{self.worker_id}] Processed: {self.stats.items_processed}", flush=True)
        print(f"[{self.worker_id}] Succeeded: {self.stats.items_succeeded}", flush=True)
        print(f"[{self.worker_id}] Failed: {self.stats.items_failed}", flush=True)
        print(f"[{self.worker_id}] Avg time: {avg_time:.2f}s", flush=True)
        print(f"[{self.worker_id}] Avg T/s: {avg_tps:.1f}", flush=True)
        print(f"[{self.worker_id}] Backend: {self.ollama_url}", flush=True)


def main():
    """Entry point for pool worker."""
    try:
        worker = PoolWorker()
        worker.run()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Required environment variables:", file=sys.stderr)
        print("  LLMC_WORKER_ID     - Unique worker identifier (e.g., 'athena')", file=sys.stderr)
        print("  LLMC_WORKER_HOST   - Ollama server hostname (e.g., 'athena')", file=sys.stderr)
        print("  LLMC_WORKER_PORT   - Ollama port (default: 11434)", file=sys.stderr)
        print("  LLMC_WORKER_MODEL  - Model name (e.g., 'qwen3:4b-instruct')", file=sys.stderr)
        print("", file=sys.stderr)
        print("Example:", file=sys.stderr)
        print("  LLMC_WORKER_ID=athena \\", file=sys.stderr)
        print("  LLMC_WORKER_HOST=athena \\", file=sys.stderr)
        print("  LLMC_WORKER_PORT=11434 \\", file=sys.stderr)
        print("  LLMC_WORKER_MODEL=qwen3:4b-instruct \\", file=sys.stderr)
        print("  python3 -m llmc.rag.pool_worker", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        log.exception(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
