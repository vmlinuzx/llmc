"""
Health checking for LLMC RAG Service.

Checks Ollama endpoint availability and latency.
"""

from dataclasses import dataclass
import json
import logging
import os
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


@dataclass
class OllamaEndpoint:
    """Represents an Ollama endpoint."""

    label: str
    url: str
    model: str


@dataclass
class HealthStatus:
    """Health check result for an endpoint."""

    endpoint: OllamaEndpoint
    reachable: bool
    latency_ms: float
    error: str = ""


class HealthChecker:
    """Performs health checks on Ollama endpoints."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def check_endpoint(self, endpoint: OllamaEndpoint) -> HealthStatus:
        """Ping an Ollama endpoint with minimal request."""
        start = time.time()

        payload = json.dumps(
            {"model": endpoint.model, "prompt": "ping", "stream": False}
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{endpoint.url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                _ = resp.read(1)  # Just check we got bytes back

            latency_ms = (time.time() - start) * 1000
            return HealthStatus(
                endpoint=endpoint, reachable=True, latency_ms=latency_ms
            )

        except Exception as e:
            return HealthStatus(
                endpoint=endpoint, reachable=False, latency_ms=0, error=str(e)
            )

    def check_all(self, endpoints: list[OllamaEndpoint]) -> list[HealthStatus]:
        """Check all endpoints."""
        return [self.check_endpoint(ep) for ep in endpoints]

    def format_results(self, results: list[HealthStatus]) -> str:
        """Format health check results for display."""
        output = []
        output.append("LLMC RAG Health Check")
        output.append("=" * 50)
        output.append("")

        reachable = [r for r in results if r.reachable]
        unreachable = [r for r in results if not r.reachable]

        if reachable:
            output.append("✅ Reachable Endpoints:")
            for r in reachable:
                output.append(
                    f"  {r.endpoint.label:15} {r.endpoint.url:40} ({r.latency_ms:.0f}ms)"
                )

        if unreachable:
            output.append("")
            output.append("❌ Unreachable Endpoints:")
            for r in unreachable:
                output.append(f"  {r.endpoint.label:15} {r.endpoint.url:40}")
                output.append(f"    Error: {r.error}")

        output.append("")
        output.append(f"Summary: {len(reachable)}/{len(results)} endpoints healthy")

        return "\n".join(output)


def _validate_url(url: str) -> tuple[bool, str]:
    """
    Validate a URL for safe use in health checks.
    
    Returns:
        Tuple of (is_valid, validated_url_or_error_message)
    """
    try:
        parsed = urllib.parse.urlparse(url)
        
        # SECURITY: Only allow http/https schemes
        if parsed.scheme not in ("http", "https"):
            return False, f"Invalid URL scheme '{parsed.scheme}'. Only http/https allowed."
        
        # Must have a hostname
        if not parsed.hostname:
            return False, "URL must have a hostname."
        
        # Warn about potentially dangerous internal hostnames
        hostname = parsed.hostname.lower()
        internal_prefixes = ("127.", "10.", "192.168.", "172.16.", "172.17.", 
                            "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
                            "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
                            "172.28.", "172.29.", "172.30.", "172.31.")
        internal_names = ("localhost", "host.docker.internal", "kubernetes.default")
        
        if hostname in internal_names or any(hostname.startswith(p) for p in internal_prefixes):
            logger.warning(
                f"SSRF Warning: URL '{url}' points to internal/localhost address. "
                "This is allowed but could be used for internal network scanning."
            )
        
        return True, url
        
    except Exception as e:
        return False, f"Failed to parse URL: {e}"


def parse_ollama_hosts_from_env() -> list[OllamaEndpoint]:
    """Parse ENRICH_OLLAMA_HOSTS environment variable with URL validation."""
    raw = os.getenv("ENRICH_OLLAMA_HOSTS", "")
    if not raw:
        return []

    endpoints: list[OllamaEndpoint] = []
    model = os.getenv("ENRICH_MODEL", "qwen3:4b-instruct")

    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue

        if "=" in part:
            label, url = part.split("=", 1)
        else:
            label, url = "", part

        label = label.strip() or f"host{len(endpoints) + 1}"
        url = url.strip()

        # Add default scheme if not present
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        # SECURITY: Validate URL before adding
        is_valid, result = _validate_url(url)
        if not is_valid:
            logger.warning(f"Skipping invalid Ollama host '{label}': {result}")
            continue

        endpoints.append(OllamaEndpoint(label=label, url=url.rstrip("/"), model=model))

    return endpoints
