"""Ollama backend adapter for enrichment."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from llmc.rag.config_enrichment import EnrichmentBackendSpec
from llmc.rag.enrichment_backends import BackendError

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
        connect_timeout = (spec.options or {}).get("connect_timeout", 10.0)
        
        client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
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
        # Build options - support keep_alive from config or default to immediate unload
        options = dict(self.spec.options or {})
        if "keep_alive" not in options:
            options["keep_alive"] = "0"  # Unload model immediately after generation
        
        payload = {
            "model": self.spec.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
            "keep_alive": options.pop("keep_alive"),  # keep_alive is top-level, not in options
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
        
        # Parse response - Qwen3 uses "thinking" field for chain-of-thought
        # Combine both fields to handle models that split content
        raw_text = data.get("response", "")
        thinking_text = data.get("thinking", "")
        
        # If response is empty but thinking has content, use thinking
        # This handles Qwen3's "thinking" mode where response is often empty
        if not raw_text.strip() and thinking_text.strip():
            raw_text = thinking_text
        
        result = self._parse_enrichment(raw_text, item)
        
        # Calculate tokens per second
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        tokens_per_sec = 0.0
        if eval_duration_ns > 0 and eval_count > 0:
            tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
        
        meta = {
            "model": data.get("model"),
            "host": self.spec.url,
            "eval_count": eval_count,
            "eval_duration": eval_duration_ns,
            "prompt_eval_count": data.get("prompt_eval_count"),
            "total_duration": data.get("total_duration"),
            "tokens_per_second": round(tokens_per_sec, 1),
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
                return dict(json.loads(fence_match.group(1)))
            except json.JSONDecodeError:
                pass
        
        # Second try: find the full JSON object (handles nesting)
        # Find the first '{' and then match braces to find the complete object
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                # Handle string escaping
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                    
                # Track if we're inside a string
                if char == '"':
                    in_string = not in_string
                    continue
                    
                # Only count braces outside of strings
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the complete JSON object
                            json_str = text[start_idx:i+1]
                            try:
                                return dict(json.loads(json_str))
                            except json.JSONDecodeError:
                                break
        
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
