"""
Clinical Relation Extraction Module

Extracts clinical relationships from medical text using pattern matching.
Supports edge types: TREATED_BY, MONITORED_BY, CONTRAINDICATES, ADVERSE_EVENT
"""
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from ..graph.edge_types import EdgeType


@dataclass
class ClinicalRelation:
    """Represents a clinical relationship extracted from text."""
    source_entity: str
    target_entity: str
    edge_type: EdgeType
    confidence: float
    context: str
    matched_pattern: str


class ClinicalRelationExtractor:
    """Extracts clinical relationships using pattern matching."""
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self.patterns = self._build_patterns()
    
    def _build_patterns(self) -> List[Tuple[str, EdgeType, float]]:
        """Build regex patterns for clinical relation extraction."""
        patterns = [
            # TREATED_BY patterns
            (r'(?i)(\w+(?: \w+)*) (?:is treated with|can be treated with|treated by|managed with) (\w+(?: \w+)*)', 
             EdgeType.TREATED_BY, 0.9),
            (r'(?i)(\w+(?: \w+)*) (?:treatment includes|therapy includes) (\w+(?: \w+)*)', 
             EdgeType.TREATED_BY, 0.8),
            (r'(?i)(\w+(?: \w+)*) (?:responds to|improves with) (\w+(?: \w+)*)', 
             EdgeType.TREATED_BY, 0.7),
            
            # MONITORED_BY patterns
            (r'(?i)(\w+(?: \w+)*) (?:is monitored with|monitored by|followed with) (\w+(?: \w+)*)', 
             EdgeType.MONITORED_BY, 0.9),
            (r'(?i)(\w+(?: \w+)*) (?:requires monitoring with|monitoring includes) (\w+(?: \w+)*)', 
             EdgeType.MONITORED_BY, 0.8),
            (r'(?i)(\w+(?: \w+)*) (?:tracked with|assessed with) (\w+(?: \w+)*)', 
             EdgeType.MONITORED_BY, 0.7),
            
            # CONTRAINDICATES patterns
            (r'(?i)(\w+(?: \w+)*) (?:is contraindicated in|contraindicated for|should not be used in) (\w+(?: \w+)*)', 
             EdgeType.CONTRAINDICATES, 0.9),
            (r'(?i)(\w+(?: \w+)*) (?:is not recommended for|avoid in) (\w+(?: \w+)*)', 
             EdgeType.CONTRAINDICATES, 0.8),
            (r'(?i)(\w+(?: \w+)*) (?:may worsen|can exacerbate) (\w+(?: \w+)*)', 
             EdgeType.CONTRAINDICATES, 0.7),
            
            # ADVERSE_EVENT patterns
            (r'(?i)(\w+(?: \w+)*) (?:causes|may cause|can cause) (\w+(?: \w+)*)', 
             EdgeType.ADVERSE_EVENT, 0.9),
            (r'(?i)(\w+(?: \w+)*) (?:side effects include|adverse effects include) (\w+(?: \w+)*)', 
             EdgeType.ADVERSE_EVENT, 0.8),
            (r'(?i)(\w+(?: \w+)*) (?:is associated with|linked to) (\w+(?: \w+)*) (?:as side effect|as adverse event)', 
             EdgeType.ADVERSE_EVENT, 0.7),
        ]
        return patterns
    
    def extract_from_text(self, text: str) -> List[ClinicalRelation]:
        """Extract clinical relations from text."""
        relations = []
        
        for pattern_str, edge_type, base_confidence in self.patterns:
            matches = re.finditer(pattern_str, text)
            for match in matches:
                source = match.group(1).strip()
                target = match.group(2).strip()
                
                # Calculate confidence based on match quality
                confidence = self._calculate_confidence(base_confidence, match)
                
                if confidence >= self.confidence_threshold:
                    relation = ClinicalRelation(
                        source_entity=source,
                        target_entity=target,
                        edge_type=edge_type,
                        confidence=confidence,
                        context=match.group(0),
                        matched_pattern=pattern_str
                    )
                    relations.append(relation)
        
        return relations
    
    def _calculate_confidence(self, base_confidence: float, match: re.Match) -> float:
        """Calculate confidence score based on match characteristics."""
        confidence = base_confidence
        
        # Adjust confidence based on match length (longer matches are more specific)
        match_text = match.group(0)
        if len(match_text.split()) > 5:
            confidence += 0.1
        elif len(match_text.split()) < 3:
            confidence -= 0.1
        
        # Cap confidence between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    def extract_from_documents(self, documents: List[str]) -> List[ClinicalRelation]:
        """Extract clinical relations from multiple documents."""
        all_relations = []
        for doc in documents:
            relations = self.extract_from_text(doc)
            all_relations.extend(relations)
        return all_relations


def extract_relations_with_threshold(
    text: str, 
    confidence_threshold: float = 0.7
) -> List[ClinicalRelation]:
    """Convenience function to extract relations with custom threshold."""
    extractor = ClinicalRelationExtractor(confidence_threshold=confidence_threshold)
    return extractor.extract_from_text(text)
