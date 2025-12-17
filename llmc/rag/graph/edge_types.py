from enum import Enum


class EdgeType(str, Enum):
    """Valid edge types for tech docs graph."""
    REFERENCES = "REFERENCES"      # Section cross-references
    REQUIRES = "REQUIRES"          # Prerequisite dependency
    RELATED_TO = "RELATED_TO"      # Topical relationship
    SUPERSEDES = "SUPERSEDES"      # Version relationship
    WARNS_ABOUT = "WARNS_ABOUT"    # Warning/caution relationship
    # Clinical edge types
    TREATED_BY = "TREATED_BY"      # Condition is treated by medication/procedure
    MONITORED_BY = "MONITORED_BY"  # Condition is monitored by test/lab
    CONTRAINDICATES = "CONTRAINDICATES"  # Drug contraindicates condition
    ADVERSE_EVENT = "ADVERSE_EVENT"  # Drug causes adverse event
