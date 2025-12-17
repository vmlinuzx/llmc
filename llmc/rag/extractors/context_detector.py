import re

class ContextDetector:
    def __init__(self):
        # Negation patterns
        self.negation_patterns = [
            r'\bno\b',
            r'\bnot\b',
            r'\bdenies\b',
            r'\bwithout\b',
            r'\bnegative for\b',
            r'\bruled out\b',
            r'\bexcluded\b',
            r'\babsence of\b',
            r'\bfree of\b',
            r'\bnever had\b',
            r'\bno evidence of\b',
            r'\bno sign of\b'
        ]
        
        # Historical patterns
        self.historical_patterns = [
            r'\bhistory of\b',
            r'\bprior\b',
            r'\bprevious\b',
            r'\bpast\b',
            r'\bformerly\b',
            r'\bwas\b',
            r'\bwere\b',
            r'\bhad\b',
            r'\bdiagnosed with\b',
            r'\btreated for\b'
        ]
        
        # Family history patterns
        self.family_patterns = [
            r'\bfamily history\b',
            r'\bfather\b',
            r'\bmother\b',
            r'\bbrother\b',
            r'\bsister\b',
            r'\bson\b',
            r'\bdaughter\b',
            r'\bparent\b',
            r'\bsibling\b',
            r'\bmother had\b',
            r'\bfather had\b',
            r'\bruns in the family\b',
            r'\bgenetic\b'
        ]
        
        # Hypothetical patterns
        self.hypothetical_patterns = [
            r'\bif\b',
            r'\bshould\b',
            r'\bconsider\b',
            r'\brule out\b',
            r'\bevaluate for\b',
            r'\bsuspect\b',
            r'\bpossible\b',
            r'\bpotential\b',
            r'\bsuspected\b',
            r'\bquestion of\b',
            r'\bmay be\b',
            r'\bcould be\b'
        ]
        
        # Compile regex patterns
        self.negation_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.negation_patterns]
        self.historical_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.historical_patterns]
        self.family_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.family_patterns]
        self.hypothetical_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.hypothetical_patterns]
        
        # Window size for context detection
        self.window_size = 50  # characters before/after entity to check
    
    def _get_context_window(self, text, entity_span):
        """Extract context window around entity span"""
        start, end = entity_span
        entity_length = end - start
        
        # Calculate window boundaries
        window_start = max(0, start - self.window_size)
        window_end = min(len(text), end + self.window_size)
        
        # Extract pre-context and post-context
        pre_context = text[window_start:start]
        post_context = text[end:window_end]
        
        return pre_context, post_context, window_start, window_end
    
    def _check_patterns_in_context(self, patterns, pre_context, post_context):
        """Check if any pattern matches in the context"""
        for pattern in patterns:
            if pattern.search(pre_context) or pattern.search(post_context):
                return True
        return False
    
    def detect_negation(self, text, entity_span):
        """
        Detect if entity is negated in the text
        
        Args:
            text: Full text string
            entity_span: Tuple of (start, end) character indices
        
        Returns:
            bool: True if entity is negated
        """
        pre_context, post_context, _, _ = self._get_context_window(text, entity_span)
        return self._check_patterns_in_context(self.negation_regex, pre_context, post_context)
    
    def detect_context(self, text, entity_span):
        """
        Detect all context categories for an entity
        
        Args:
            text: Full text string
            entity_span: Tuple of (start, end) character indices
        
        Returns:
            dict: Dictionary with context categories as keys and boolean values
        """
        pre_context, post_context, _, _ = self._get_context_window(text, entity_span)
        
        return {
            'negated': self._check_patterns_in_context(self.negation_regex, pre_context, post_context),
            'historical': self._check_patterns_in_context(self.historical_regex, pre_context, post_context),
            'family': self._check_patterns_in_context(self.family_regex, pre_context, post_context),
            'hypothetical': self._check_patterns_in_context(self.hypothetical_regex, pre_context, post_context)
        }

# Convenience functions for backward compatibility
def detect_negation(text, entity_span):
    """Convenience function to detect negation"""
    detector = ContextDetector()
    return detector.detect_negation(text, entity_span)

def detect_context(text, entity_span):
    """Convenience function to detect all context categories"""
    detector = ContextDetector()
    return detector.detect_context(text, entity_span)

