"""
PHI (Protected Health Information) detector for HIPAA Safe Harbor identifiers.

This module provides regex-based detection of common PHI elements in text.
"""

from dataclasses import dataclass
import re


@dataclass
class PHIMatch:
    """Represents a single PHI match in text."""

    start: int
    end: int
    type: str
    text: str


class PHIDetector:
    """Detects Protected Health Information in text using regex patterns.

    Implements patterns for HIPAA Safe Harbor identifiers:
    - Names
    - Dates (various formats)
    - Social Security Numbers
    - Phone numbers
    - Email addresses
    - Medical Record Numbers (MRN)
    - IP addresses
    """

    def __init__(self):
        # Compile all regex patterns
        self.patterns = [
            # Social Security Number (SSN): 123-45-6789 or 123 45 6789
            (r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b", "SSN"),
            # Phone numbers: (123) 456-7890, 123-456-7890, 123.456.7890, +1-123-456-7890
            (r"\b(?:\(\d{3}\)\s?|\d{3}[-\s.]?)?\d{3}[-\s.]?\d{4}\b", "PHONE"),
            (r"\b\+\d{1,3}[-\s.]?\d{3}[-\s.]?\d{3}[-\s.]?\d{4}\b", "PHONE"),
            # Email addresses
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
            # Dates: MM/DD/YYYY, MM-DD-YYYY, YYYY/MM/DD, etc.
            (r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])[-/]\d{4}\b", "DATE"),
            (r"\b\d{4}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b", "DATE"),
            (
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
                "DATE",
            ),
            # Medical Record Numbers (MRN): often 6-10 digits, sometimes with letters
            (r"\bMRN\s*[:#]?\s*[A-Z0-9]{6,12}\b", "MRN"),
            (r"\b[A-Z0-9]{6,12}\s*\(MRN\)\b", "MRN"),
            # IP addresses (v4)
            (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP"),
            # Names: Common English first names followed by last names
            # This is a simplified pattern and may have false positives
            (
                r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)?\s*(?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){1,2}\b",
                "NAME",
            ),
        ]

        # Compile all patterns for efficiency
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), ptype)
            for pattern, ptype in self.patterns
        ]

    def detect(self, text: str) -> list[tuple[int, int, str]]:
        """Detect all PHI elements in the given text.

        Args:
            text: The input text to scan for PHI.

        Returns:
            A list of tuples (start, end, type) for each detected PHI element.
            The list is sorted by start position.
        """
        matches = []

        for pattern, ptype in self.compiled_patterns:
            for match in pattern.finditer(text):
                # Avoid overlapping matches by checking if this range is already covered
                start, end = match.start(), match.end()
                overlapping = False
                for s, e, _t in matches:
                    if not (end <= s or start >= e):
                        overlapping = True
                        break
                if not overlapping:
                    matches.append((start, end, ptype))

        # Sort by start position
        matches.sort(key=lambda x: x[0])
        return matches

    def detect_with_text(self, text: str) -> list[PHIMatch]:
        """Detect PHI elements and return match objects with the matched text.

        Args:
            text: The input text to scan.

        Returns:
            A list of PHIMatch objects with start, end, type, and text.
        """
        raw_matches = self.detect(text)
        return [
            PHIMatch(start=start, end=end, type=type_, text=text[start:end])
            for start, end, type_ in raw_matches
        ]
