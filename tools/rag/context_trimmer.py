"""Smart Context Window Management

Implements automatic context trimming strategies based on token budgets,
relevance ranking, and intelligent chunk filtering.

Architecture (from research):
1. Hybrid retrieval (BM25 + embeddings)
2. Reranking (optional ColBERT or LLM-based)
3. Diversity filtering (MMR)
4. Token budget enforcement

Design philosophy: Local-first, sub-300ms latency, <1GB memory footprint
"""

from __future__ import annotations

import tiktoken
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict


@dataclass
class ChunkItem:
    """A chunk candidate for context inclusion."""
    content: str
    file_path: Path
    symbol: str
    kind: str
    relevance_score: float = 0.0
    bm25_score: float = 0.0
    embedding_score: float = 0.0
    rerank_score: Optional[float] = None
    token_count: int = 0


@dataclass
class ContextBudget:
    """Token budget configuration for a context window."""
    max_tokens: int
    reserved_system: int = 500  # Reserved for system prompts
    reserved_user: int = 200    # Reserved for user query
    safety_margin: float = 0.1  # 10% safety buffer
    
    @property
    def available_for_chunks(self) -> int:
        """Calculate tokens available for retrieved chunks."""
        total_reserved = self.reserved_system + self.reserved_user
        usable = self.max_tokens - total_reserved
        return int(usable * (1 - self.safety_margin))


@dataclass
class TrimConfig:
    """Configuration for context trimming strategy."""
    budget: ContextBudget
    enable_mmr: bool = True
    mmr_lambda: float = 0.7  # Balance relevance vs diversity (0.7 = 70% relevance)
    enable_reranking: bool = False  # Disabled by default (requires model)
    min_relevance_threshold: float = 0.3  # Drop chunks below this score
    tokenizer_name: str = "cl100k_base"  # OpenAI's tokenizer


class ContextTrimmer:
    """Manages intelligent context window trimming."""
    
    def __init__(self, config: TrimConfig):
        self.config = config
        try:
            self.tokenizer = tiktoken.get_encoding(config.tokenizer_name)
        except Exception:
            # Fallback to basic estimation (4 chars per token)
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or fallback estimation."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback: rough estimation
            return len(text) // 4
    
    def trim_to_budget(
        self,
        chunks: List[ChunkItem],
        query: str = ""
    ) -> Tuple[List[ChunkItem], Dict[str, any]]:
        """Trim chunks to fit within token budget.
        
        Args:
            chunks: List of candidate chunks (pre-scored and sorted by relevance)
            query: User query for MMR diversity calculation
            
        Returns:
            Tuple of (selected_chunks, stats)
        """
        # Calculate token counts
        for chunk in chunks:
            chunk.token_count = self.count_tokens(chunk.content)
        
        # Filter by minimum relevance threshold
        filtered = [
            c for c in chunks 
            if c.relevance_score >= self.config.min_relevance_threshold
        ]
        
        stats = {
            "input_chunks": len(chunks),
            "after_relevance_filter": len(filtered),
            "dropped_low_relevance": len(chunks) - len(filtered),
        }
        
        if not filtered:
            return [], stats
        
        # Apply MMR diversity if enabled
        if self.config.enable_mmr and len(filtered) > 1:
            filtered = self._apply_mmr(filtered, query)
            stats["after_mmr"] = len(filtered)
        
        # Enforce token budget (greedy selection)
        selected, budget_stats = self._enforce_budget(filtered)
        stats.update(budget_stats)
        
        return selected, stats
    
    def _apply_mmr(
        self,
        chunks: List[ChunkItem],
        query: str,
        top_k: Optional[int] = None
    ) -> List[ChunkItem]:
        """Apply Maximal Marginal Relevance for diversity.
        
        MMR formula: MMR = λ * Relevance - (1-λ) * MaxSimilarity
        
        Args:
            chunks: Candidate chunks (sorted by relevance)
            query: User query
            top_k: Maximum chunks to return (None = no limit)
            
        Returns:
            Diversified chunk list
        """
        if not chunks:
            return []
        
        lambda_param = self.config.mmr_lambda
        selected: List[ChunkItem] = []
        remaining = chunks.copy()
        
        # Always include the top candidate
        selected.append(remaining.pop(0))
        
        # Iteratively select most diverse chunks
        max_iterations = top_k if top_k else len(remaining)
        for _ in range(min(max_iterations, len(remaining))):
            if not remaining:
                break
            
            best_score = -float('inf')
            best_idx = 0
            
            for idx, candidate in enumerate(remaining):
                # Relevance component
                relevance = candidate.relevance_score
                
                # Similarity to already selected (use content overlap as proxy)
                max_sim = max(
                    self._simple_similarity(candidate.content, s.content)
                    for s in selected
                )
                
                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            selected.append(remaining.pop(best_idx))
        
        return selected
    
    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Simple Jaccard similarity for diversity calculation.
        
        Note: This is a lightweight approximation. For production use with
        embeddings, replace with cosine similarity on embedding vectors.
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _enforce_budget(
        self,
        chunks: List[ChunkItem]
    ) -> Tuple[List[ChunkItem], Dict[str, any]]:
        """Enforce token budget with greedy selection.
        
        Args:
            chunks: Candidate chunks (pre-sorted by relevance/MMR)
            
        Returns:
            Tuple of (selected_chunks, budget_stats)
        """
        budget = self.config.budget.available_for_chunks
        selected: List[ChunkItem] = []
        total_tokens = 0
        
        for chunk in chunks:
            if total_tokens + chunk.token_count <= budget:
                selected.append(chunk)
                total_tokens += chunk.token_count
            else:
                # Budget exceeded, stop
                break
        
        stats = {
            "selected_chunks": len(selected),
            "total_tokens": total_tokens,
            "budget_limit": budget,
            "utilization_pct": round(total_tokens / budget * 100, 1) if budget > 0 else 0,
            "dropped_budget_exceeded": len(chunks) - len(selected),
        }
        
        return selected, stats


def create_default_config(max_tokens: int = 8192) -> TrimConfig:
    """Create a sensible default configuration.
    
    Args:
        max_tokens: Model context window size (e.g., 4096, 8192, 128000)
        
    Returns:
        TrimConfig with defaults optimized for local-first operation
    """
    budget = ContextBudget(
        max_tokens=max_tokens,
        reserved_system=500,
        reserved_user=200,
        safety_margin=0.1,
    )
    
    return TrimConfig(
        budget=budget,
        enable_mmr=True,
        mmr_lambda=0.7,
        enable_reranking=False,  # Optional advanced feature
        min_relevance_threshold=0.3,
        tokenizer_name="cl100k_base",
    )



def search_with_trimming(
    query: str,
    *,
    max_tokens: int = 8192,
    limit: int = 20,
    repo_root: Optional[Path] = None,
    model_override: Optional[str] = None,
    config: Optional[TrimConfig] = None,
) -> Tuple[List[ChunkItem], Dict[str, any]]:
    """Search and trim results to fit within token budget.
    
    This is the main entry point for smart context window management.
    It performs the full pipeline:
    1. Retrieve chunks via embedding similarity
    2. Score and rank by relevance
    3. Apply MMR diversity filtering
    4. Enforce token budget
    
    Args:
        query: User search query
        max_tokens: Maximum context window size
        limit: Initial retrieval limit (before trimming)
        repo_root: Repository root (auto-detected if None)
        model_override: Embedding model override
        config: Custom trimming configuration (uses defaults if None)
        
    Returns:
        Tuple of (selected_chunks, stats_dict)
        
    Example:
        >>> chunks, stats = search_with_trimming(
        ...     "authentication logic",
        ...     max_tokens=4096,
        ...     limit=30
        ... )
        >>> print(f"Selected {len(chunks)} chunks using {stats['total_tokens']} tokens")
    """
    from .search import search_spans
    from .utils import find_repo_root
    
    # Create default config if not provided
    if config is None:
        config = create_default_config(max_tokens=max_tokens)
    
    # Retrieve candidates
    repo = repo_root or find_repo_root()
    results = search_spans(
        query,
        limit=limit,
        repo_root=repo,
        model_override=model_override
    )
    
    # Convert to ChunkItem format
    chunks: List[ChunkItem] = []
    for result in results:
        # Read chunk content
        chunk_path = repo / result.path
        try:
            source = chunk_path.read_text(encoding='utf-8')
            # Extract lines for this chunk
            lines = source.splitlines()
            chunk_lines = lines[result.start_line - 1:result.end_line]
            content = "\n".join(chunk_lines)
        except Exception:
            # Skip if we can't read the content
            continue
        
        chunks.append(ChunkItem(
            content=content,
            file_path=result.path,
            symbol=result.symbol,
            kind=result.kind,
            relevance_score=result.score,
            embedding_score=result.score,
        ))
    
    # Apply trimming
    trimmer = ContextTrimmer(config)
    selected, stats = trimmer.trim_to_budget(chunks, query=query)
    
    return selected, stats
