"""Ollama backend adapter for enrichment."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from tools.rag.enrichment_backends import BackendAdapter, BackendError
from tools.rag.config_enrichment import EnrichmentBackendSpec

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


@dataclass
class OllamaBackend:
    """BackendAdapter implementation for Ollama.
    
    This adapter communicates with Ollama's /api/generate endpoint
    to produce enrichment summaries for code spans.
    
    Usage:
        spec = EnrichmentBackendSpec(
            name="athena",
            provider="ollama",
            model="qwen2.5:7b-instruct",
            url="http://192.168.5.20:11434",
            timeout_seconds=120,
        )
        backend = OllamaBackend.from_spec(spec)
        result, meta = backend.generate(prompt, item=span_data)
    """
    
    spec: EnrichmentBackendSpec
    client: Any  # httpx.Client
    
    @classmethod
    def from_spec(cls, spec: EnrichmentBackendSpec) -> OllamaBackend:
        """Create OllamaBackend from configuration spec.
        
        Args:
            spec: Backend specification from llmc.toml
            
        Returns:
            Configured OllamaBackend instance
            
        Raises:
            ImportError: If httpx is not installed
        """
        if httpx is None:
            raise ImportError(
                "httpx is required for OllamaBackend. "
                "Install with: pip install httpx"
            )
        
        timeout = spec.timeout_seconds or 120
        base_url = spec.url or "http://localhost:11434"
        
        client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        
        return cls(spec=spec, client=client)
    
    @property
    def config(self) -> EnrichmentBackendSpec:
        """Return backend configuration."""
        return self.spec
    
    def describe_host(self) -> str | None:
        """Return human-readable host description."""
        return self.spec.url
    
    def generate(
        self,
        prompt: str,
        *,
        item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate enrichment via Ollama API.
        
        Args:
            prompt: Enrichment prompt to send to LLM
            item: Span data dictionary (for context/debugging)
            
        Returns:
            Tuple of (result_dict, metadata_dict)
            - result_dict: Parsed enrichment with summary, key_topics, etc.
            - metadata_dict: Model info, timing, token counts
            
        Raises:
            BackendError: On timeout, HTTP error, or other failure
        """
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
            "prompt_eval_count": data.get("prompt_eval_count"),
            "total_duration": data.get("total_duration"),
        }
        
        return result, meta
    
    def _parse_enrichment(self, text: str, item: dict) -> dict[str, Any]:
        """Parse LLM output into enrichment fields.
        
        Tries to extract JSON from the response. If that fails,
        returns the raw text as a summary.
        
        Args:
            text: Raw LLM response text
            item: Original span data (for fallback)
            
        Returns:
            Dict with summary, key_topics, complexity, etc.
        """
        # Try to find JSON block in response (handles markdown fences)
        # Look for {...} or ```json\n{...}\n```
        
        # First try: look for code fence with json
        fence_match = re.search(
            r'```(?:json)?\s*\n(\{.*?\})\s*\n```',
            text,
            re.DOTALL
        )
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Second try: find bare JSON object
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback: return raw text as summary
        summary = text.strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        
        return {
            "summary": summary,
            "key_topics": [],
            "complexity": "unknown",
            "evidence": "",
        }
    
    def close(self) -> None:
        """Close HTTP client connection."""
        if self.client:
            self.client.close()
    
    def __enter__(self) -> OllamaBackend:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
