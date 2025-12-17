from dataclasses import dataclass


@dataclass
class GraphEdge:
    """Represents a relationship edge extracted from tech docs."""
    source_id: str            # Canonical span_id of source
    target_id: str            # Resolved target span_id
    edge_type: str            # REFERENCES, REQUIRES, RELATED_TO, etc.
    score: float              # 0.0-1.0 confidence score
    pattern_id: str | None = None    # Which regex pattern matched
    llm_trace_id: str | None = None  # If LLM-assisted extraction
    model_name: str | None = None    # If LLM-assisted extraction
    match_text: str = ""      # Original matched text
    
    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if edge meets confidence threshold."""
        return self.score >= threshold
    
    def is_llm_extracted(self) -> bool:
        """Check if edge was extracted using LLM."""
        return self.llm_trace_id is not None
