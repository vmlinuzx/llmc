"""
Medical Abbreviations Dictionary.
Used for expansion and normalization.
"""

from typing import Dict

MEDICAL_ABBREVIATIONS: Dict[str, str] = {
    "htn": "hypertension",
    "dm": "diabetes mellitus",
    "dm2": "type 2 diabetes mellitus",
    "t2dm": "type 2 diabetes mellitus",
    "cad": "coronary artery disease",
    "chf": "congestive heart failure",
    "copd": "chronic obstructive pulmonary disease",
    "ckd": "chronic kidney disease",
    "mi": "myocardial infarction",
    "cva": "cerebrovascular accident",
    "tia": "transient ischemic attack",
    "dvt": "deep vein thrombosis",
    "pe": "pulmonary embolism",  # Context dependent: Physical Exam vs Pulm Embolism
    "uri": "upper respiratory infection",
    "uti": "urinary tract infection",
    "gerd": "gastroesophageal reflux disease",
    
    # Medications / Prescriptions
    "bid": "twice a day",
    "tid": "three times a day",
    "qid": "four times a day",
    "qd": "every day",
    "qhs": "at bedtime",
    "prn": "as needed",
    "po": "by mouth",
    "iv": "intravenous",
    "im": "intramuscular",
    "sq": "subcutaneous",
    "mg": "milligrams",
    "mcg": "micrograms",
    "g": "grams",
    
    # Vitals
    "bp": "blood pressure",
    "hr": "heart rate",
    "rr": "respiratory rate",
    "t": "temperature",
    "wt": "weight",
    "ht": "height",
    "bmi": "body mass index",
}

def expand_abbreviation(token: str) -> str:
    """Expand a medical abbreviation if found."""
    return MEDICAL_ABBREVIATIONS.get(token.lower(), token)
