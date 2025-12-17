"""
Medical Header Lexicon and Fuzzy Matching Logic.
Defines canonical section headers and variants for clinical notes.
"""

# Canonical Section Types
SECTION_SUBJECTIVE = "subjective"
SECTION_OBJECTIVE = "objective"
SECTION_ASSESSMENT = "assessment"
SECTION_PLAN = "plan"
SECTION_HISTORY = "history"
SECTION_MEDICATIONS = "medications"
SECTION_ALLERGIES = "allergies"
SECTION_LABS = "labs"
SECTION_IMAGING = "imaging"
SECTION_PROCEDURES = "procedures"
SECTION_FINDINGS = "findings"
SECTION_IMPRESSION = "impression"
SECTION_TECHNIQUE = "technique"

# Header Variants mapping (Normalized -> List of raw variants)
HEADER_VARIANTS: dict[str, list[str]] = {
    SECTION_SUBJECTIVE: [
        "subjective",
        "history of present illness",
        "hpi",
        "chief complaint",
        "cc",
        "reason for visit",
        "review of systems",
        "ros",
    ],
    SECTION_OBJECTIVE: [
        "objective",
        "physical exam",
        "pe",
        "vitals",
        "vital signs",
        "measurements",
        "exam",
    ],
    SECTION_ASSESSMENT: [
        "assessment",
        "assessment and plan",
        "a/p",
        "diagnosis",
        "diagnoses",
        "impression",
        "clinical impression",
        "problem list",
    ],
    SECTION_PLAN: [
        "plan",
        "treatment plan",
        "recommendations",
        "follow up",
        "disposition",
    ],
    SECTION_HISTORY: [
        "past medical history",
        "pmh",
        "social history",
        "sh",
        "family history",
        "fh",
        "past surgical history",
        "psh",
    ],
    SECTION_MEDICATIONS: [
        "medications",
        "current medications",
        "meds",
        "active medications",
        "discharge medications",
    ],
    SECTION_ALLERGIES: ["allergies", "allergies/intolerances", "all"],
    SECTION_LABS: ["labs", "laboratory results", "lab results", "studies"],
    SECTION_IMAGING: ["imaging", "radiology", "studies", "x-ray", "mri", "ct"],
    SECTION_FINDINGS: ["findings", "examination"],
    SECTION_IMPRESSION: ["impression", "conclusion"],
    SECTION_TECHNIQUE: ["technique", "procedure"],
}


def normalize_header(header_text: str) -> str | None:
    """
    Normalize a header string to a canonical type.
    Uses strict matching first, then fuzzy matching (if implemented).
    """
    cleaned = header_text.strip().lower().rstrip(":")

    for section_type, variants in HEADER_VARIANTS.items():
        if cleaned in variants:
            return section_type

    # Simple fuzzy fallback (levenshtein distance could be added here)
    # For now, we check if any variant is a substring of the header
    # (careful with short abbreviations)
    for section_type, variants in HEADER_VARIANTS.items():
        for v in variants:
            if len(v) > 3 and v in cleaned:
                return section_type

    return None
