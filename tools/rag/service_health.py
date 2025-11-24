"""
Health checking for LLMC RAG Service.

Checks Ollama endpoint availability and latency.
"""
import json
import time
import urllib.request
from dataclasses import dataclass
from typing import List, Dict
import os


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
        
        payload = json.dumps({
            "model": endpoint.model,
            "prompt": "ping",
            "stream": False
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{endpoint.url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                _ = resp.read(1)  # Just check we got bytes back
            
            latency_ms = (time.time() - start) * 1000
            return HealthStatus(
                endpoint=endpoint,
                reachable=True,
                latency_ms=latency_ms
            )
        
        except Exception as e:
            return HealthStatus(
                endpoint=endpoint,
                reachable=False,
                latency_ms=0,
                error=str(e)
            )
    
    def check_all(self, endpoints: List[OllamaEndpoint]) -> List[HealthStatus]:
        """Check all endpoints."""
        return [self.check_endpoint(ep) for ep in endpoints]
    
    def format_results(self, results: List[HealthStatus]) -> str:
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
                output.append(f"  {r.endpoint.label:15} {r.endpoint.url:40} ({r.latency_ms:.0f}ms)")
        
        if unreachable:
            output.append("")
            output.append("❌ Unreachable Endpoints:")
            for r in unreachable:
                output.append(f"  {r.endpoint.label:15} {r.endpoint.url:40}")
                output.append(f"    Error: {r.error}")
        
        output.append("")
        output.append(f"Summary: {len(reachable)}/{len(results)} endpoints healthy")
        
        return "\n".join(output)



def parse_ollama_hosts_from_env() -> List[OllamaEndpoint]:
    """Parse ENRICH_OLLAMA_HOSTS environment variable."""
    raw = os.getenv("ENRICH_OLLAMA_HOSTS", "")
    if not raw:
        return []
    
    endpoints = []
    model = os.getenv("ENRICH_MODEL", "qwen2.5:7b-instruct")
    
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
        
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        
        endpoints.append(OllamaEndpoint(
            label=label,
            url=url.rstrip("/"),
            model=model
        ))
    
    return endpoints
