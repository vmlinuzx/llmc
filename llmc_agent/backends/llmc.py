"""LLMC RAG backend for llmc_agent.

Integrates with LLMC's semantic code search for context enrichment.
Falls back to ripgrep if LLMC is unavailable.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RAGResult:
    """A single RAG search result."""
    
    path: str
    start_line: int
    end_line: int
    score: float
    snippet: str
    summary: str | None = None


class LLMCBackend:
    """Integration with LLMC's RAG system."""
    
    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = self._find_repo_root(repo_root)
        self._llmc_available: bool | None = None
    
    def _find_repo_root(self, configured: str | Path | None) -> Path | None:
        """Find the LLMC-enabled repo root."""
        
        if configured and str(configured) != "auto":
            path = Path(configured)
            if (path / ".llmc").exists() or (path / "llmc.toml").exists():
                return path
            return None
        
        # Walk up from cwd looking for .llmc/ or llmc.toml
        current = Path.cwd()
        while current != current.parent:
            if (current / ".llmc").exists() or (current / "llmc.toml").exists():
                return current
            current = current.parent
        
        return None
    
    @property
    def available(self) -> bool:
        """Check if LLMC is available."""
        if self._llmc_available is None:
            self._llmc_available = self._check_llmc_available()
        return self._llmc_available
    
    def _check_llmc_available(self) -> bool:
        """Check if llmc-cli is available and repo is indexed."""
        if not self.repo_root:
            return False
        
        try:
            result = subprocess.run(
                ["llmc-cli", "analytics", "stats"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.repo_root,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> list[RAGResult]:
        """Search using LLMC's RAG system."""
        
        if not self.repo_root:
            return []
        
        if self.available:
            results = await self._llmc_search(query, limit, min_score)
            if results:
                return results
        
        # Fall back to ripgrep
        return await self._fallback_search(query, limit)
    
    async def _llmc_search(
        self,
        query: str,
        limit: int,
        min_score: float,
    ) -> list[RAGResult]:
        """Search using llmc-cli."""
        try:
            # Use llmc-cli analytics search
            result = subprocess.run(
                [
                    "llmc-cli", "analytics", "search",
                    query,
                    "--limit", str(limit),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_root,
            )
            
            if result.returncode != 0:
                return []
            
            # Parse JSON output
            import json
            try:
                data = json.loads(result.stdout)
                results = []
                
                for item in data.get("results", data) if isinstance(data, dict) else data:
                    # Handle various output formats
                    if isinstance(item, dict):
                        score = item.get("score", 0.5)
                        if score < min_score:
                            continue
                        
                        results.append(RAGResult(
                            path=item.get("path", item.get("file", "")),
                            start_line=item.get("start_line", item.get("line", 1)),
                            end_line=item.get("end_line", item.get("line", 1)),
                            score=score,
                            snippet=item.get("snippet", item.get("content", ""))[:500],
                            summary=item.get("summary"),
                        ))
                
                return results[:limit]
            except json.JSONDecodeError:
                # Try line-based parsing as fallback
                return self._parse_llmc_text_output(result.stdout, limit)
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
    
    def _parse_llmc_text_output(self, output: str, limit: int) -> list[RAGResult]:
        """Parse non-JSON llmc output."""
        results = []
        
        for line in output.strip().splitlines()[:limit]:
            # Try to parse "path:line: content" format
            if ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    try:
                        path = parts[0]
                        line_num = int(parts[1]) if parts[1].isdigit() else 1
                        snippet = parts[2].strip() if len(parts) > 2 else ""
                        
                        results.append(RAGResult(
                            path=path,
                            start_line=line_num,
                            end_line=line_num,
                            score=0.5,
                            snippet=snippet,
                            summary=None,
                        ))
                    except (ValueError, IndexError):
                        continue
        
        return results
    
    async def _fallback_search(self, query: str, limit: int) -> list[RAGResult]:
        """Fallback to ripgrep when LLMC is unavailable."""
        
        if not self.repo_root:
            return []
        
        try:
            # Use ripgrep with context
            result = subprocess.run(
                [
                    "rg",
                    "--json",
                    "-i",  # case insensitive
                    "-C", "2",  # 2 lines context
                    "--max-count", str(limit * 3),  # get more, then dedupe
                    query,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.repo_root,
            )
            
            if result.returncode not in (0, 1):  # 1 = no matches, OK
                return []
            
            import json
            results = []
            seen_files: set[str] = set()
            
            for line in result.stdout.splitlines():
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        path = match_data.get("path", {}).get("text", "")
                        
                        # Dedupe by file
                        if path in seen_files:
                            continue
                        seen_files.add(path)
                        
                        line_num = match_data.get("line_number", 1)
                        text = match_data.get("lines", {}).get("text", "")
                        
                        results.append(RAGResult(
                            path=path,
                            start_line=line_num,
                            end_line=line_num,
                            score=0.4,  # Lower score for fallback
                            snippet=text.strip()[:500],
                            summary=None,
                        ))
                        
                        if len(results) >= limit:
                            break
                
                except json.JSONDecodeError:
                    continue
            
            return results
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Last resort: basic rg -l
            return await self._basic_file_search(query, limit)
    
    async def _basic_file_search(self, query: str, limit: int) -> list[RAGResult]:
        """Most basic fallback: just list matching files."""
        try:
            result = subprocess.run(
                ["rg", "-l", "-i", query, "."],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.repo_root,
            )
            
            files = result.stdout.strip().splitlines()[:limit]
            return [
                RAGResult(
                    path=f,
                    start_line=1,
                    end_line=1,
                    score=0.3,
                    snippet="",
                    summary=None,
                )
                for f in files
            ]
        except Exception:
            return []


def format_rag_results(results: list[RAGResult], include_summary: bool = True) -> str:
    """Format RAG results for inclusion in prompt."""
    
    if not results:
        return ""
    
    lines = ["[Relevant code from the repository:]", ""]
    
    for r in results:
        lines.append(f"**{r.path}** (lines {r.start_line}-{r.end_line}, score: {r.score:.2f})")
        
        if r.summary and include_summary:
            lines.append(f"Summary: {r.summary}")
        
        if r.snippet:
            lines.append("```")
            lines.append(r.snippet)
            lines.append("```")
        
        lines.append("")
    
    return "\n".join(lines)
