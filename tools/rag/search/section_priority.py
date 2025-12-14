"""
Section priority and boosting utilities for medical search.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import re

@dataclass
class SearchResult:
    """Represents a search result with section information."""
    doc_id: str
    section_id: str
    content: str
    score: float
    metadata: Dict[str, str]

class SectionPriority:
    """Defines weight mappings for different medical sections."""
    
    # Default weight mappings for common medical sections
    DEFAULT_WEIGHTS = {
        "IMPRESSION": 1.0,
        "CONCLUSION": 1.0,
        "ASSESSMENT": 0.9,
        "DIAGNOSIS": 0.9,
        "FINDINGS": 0.8,
        "RESULTS": 0.8,
        "SUBJECTIVE": 0.7,
        "OBJECTIVE": 0.7,
        "PLAN": 0.6,
        "RECOMMENDATIONS": 0.6,
        "TECHNIQUE": 0.3,
        "METHOD": 0.3,
        "PROCEDURE": 0.4,
        "HISTORY": 0.5,
        "BACKGROUND": 0.4,
        "OTHER": 0.2
    }
    
    @classmethod
    def get_weight(cls, section_type: str) -> float:
        """Get weight for a given section type."""
        # Normalize section type to uppercase
        normalized = section_type.upper().strip()
        return cls.DEFAULT_WEIGHTS.get(normalized, 0.2)
    
    @classmethod
    def boost_by_section(cls, results: List[SearchResult], 
                         section_weights: Optional[Dict[str, float]] = None) -> List[SearchResult]:
        """
        Boost search results based on their section type.
        
        Args:
            results: List of search results
            section_weights: Optional custom weight mapping. If None, uses DEFAULT_WEIGHTS
            
        Returns:
            List of results with boosted scores
        """
        if not results:
            return results
        
        # Use custom weights or default
        weights = section_weights if section_weights is not None else cls.DEFAULT_WEIGHTS
        
        boosted_results = []
        for result in results:
            # Get section type from metadata
            section_type = result.metadata.get("section_type", "OTHER")
            normalized_type = section_type.upper().strip()
            
            # Get weight
            weight = weights.get(normalized_type, 0.2)
            
            # Apply boost
            boosted_score = result.score * weight
            
            # Create new result with boosted score
            boosted_result = SearchResult(
                doc_id=result.doc_id,
                section_id=result.section_id,
                content=result.content,
                score=boosted_score,
                metadata=result.metadata.copy()
            )
            boosted_results.append(boosted_result)
        
        # Sort by boosted score in descending order
        boosted_results.sort(key=lambda x: x.score, reverse=True)
        return boosted_results
    
    @classmethod
    def negation_aware_boost(cls, results: List[SearchResult]) -> List[SearchResult]:
        """
        Boost results based on negation detection.
        Affirmed findings are ranked higher than negated ones.
        
        Args:
            results: List of search results
            
        Returns:
            List of results with negation-aware boosting applied
        """
        if not results:
            return results
        
        # Patterns indicating negation
        negation_patterns = [
            r'\bno\s+evidence\s+of\b',
            r'\brules?\s+out\b',
            r'\bnegative\s+for\b',
            r'\bdenies\b',
            r'\bwithout\b',
            r'\bnot\s+(?:present|seen|identified|detected)\b',
            r'\babsence\s+of\b',
            r'\bexcluded\b'
        ]
        
        # Patterns indicating affirmation
        affirmation_patterns = [
            r'\bpositive\s+for\b',
            r'\bconfirmed\b',
            r'\bevidence\s+of\b',
            r'\bconsistent\s+with\b',
            r'\bshows\b',
            r'\bdemonstrates\b',
            r'\bfindings\s+suggest\b',
            r'\bindicates\b'
        ]
        
        boosted_results = []
        for result in results:
            content = result.content.lower()
            
            # Check for negation
            is_negated = any(re.search(pattern, content) for pattern in negation_patterns)
            
            # Check for affirmation
            is_affirmed = any(re.search(pattern, content) for pattern in affirmation_patterns)
            
            # Apply boosting factors
            boost_factor = 1.0
            if is_negated:
                # Demote negated findings
                boost_factor = 0.3
            elif is_affirmed:
                # Promote affirmed findings
                boost_factor = 1.5
            
            # Also apply section-based weight
            section_type = result.metadata.get("section_type", "OTHER")
            section_weight = cls.get_weight(section_type)
            
            # Combined boost
            final_score = result.score * boost_factor * section_weight
            
            # Update metadata with negation info
            metadata = result.metadata.copy()
            metadata["negation_detected"] = str(is_negated)
            metadata["affirmation_detected"] = str(is_affirmed)
            
            boosted_result = SearchResult(
                doc_id=result.doc_id,
                section_id=result.section_id,
                content=result.content,
                score=final_score,
                metadata=metadata
            )
            boosted_results.append(boosted_result)
        
        # Sort by final score
        boosted_results.sort(key=lambda x: x.score, reverse=True)
        return boosted_results
