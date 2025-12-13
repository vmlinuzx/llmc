from enum import Enum


class EdgeType(str, Enum):
    """Valid edge types for tech docs graph."""
    REFERENCES = "REFERENCES"      # Section cross-references
    REQUIRES = "REQUIRES"          # Prerequisite dependency
    RELATED_TO = "RELATED_TO"      # Topical relationship
    SUPERSEDES = "SUPERSEDES"      # Version relationship
    WARNS_ABOUT = "WARNS_ABOUT"    # Warning/caution relationship
