"""
Ontology Loaders and Lookup with semantic-type filters.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class OntologyLoader:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.icd10: dict[str, str] = {}
        self.rxnorm: dict[str, str] = {}
        self.snomed: dict[str, str] = {}
        self.loinc: dict[str, str] = {}

        # Semantic type mappings
        self.icd10_semantic: dict[str, list[str]] = {}
        self.rxnorm_semantic: dict[str, list[str]] = {}
        self.snomed_semantic: dict[str, list[str]] = {}
        self.loinc_semantic: dict[str, list[str]] = {}

        # Reverse lookups
        self.icd10_rev: dict[str, str] = {}
        self.rxnorm_rev: dict[str, str] = {}
        self.snomed_rev: dict[str, str] = {}
        self.loinc_rev: dict[str, str] = {}

    def load_all(self):
        """Load all ontologies from JSON files and initialize semantic types."""
        self.icd10 = self._load_json("icd10cm_2024.json")
        self.rxnorm = self._load_json("rxnorm_2024.json")
        self.snomed = self._load_json("snomed_us_2024.json")
        self.loinc = self._load_json("loinc_2024.json")

        # Build reverse lookups (Term -> Code) for simple matching
        self.icd10_rev = {v.lower(): k for k, v in self.icd10.items()}
        self.rxnorm_rev = {v.lower(): k for k, v in self.rxnorm.items()}
        self.snomed_rev = {v.lower(): k for k, v in self.snomed.items()}
        self.loinc_rev = {v.lower(): k for k, v in self.loinc.items()}

        # Initialize semantic types
        self._init_semantic_types()

    def _load_json(self, filename: str) -> dict[str, str]:
        p = self.config_dir / filename
        if p.exists():
            try:
                with open(p) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _init_semantic_types(self):
        """Initialize semantic type mappings for each ontology."""
        # ICD-10 semantic types based on code prefixes
        for code in self.icd10:
            if code.startswith("E"):
                self.icd10_semantic[code] = ["Endocrine", "Metabolic", "Nutritional"]
            elif code.startswith("I"):
                self.icd10_semantic[code] = ["Cardiovascular", "Circulatory"]
            elif code.startswith("J"):
                self.icd10_semantic[code] = ["Respiratory"]
            elif code.startswith("M"):
                self.icd10_semantic[code] = ["Musculoskeletal", "Connective Tissue"]
            else:
                self.icd10_semantic[code] = ["Disease"]

        # RxNorm semantic types based on description keywords
        for code, desc in self.rxnorm.items():
            desc_lower = desc.lower()
            types = ["Drug"]
            if any(word in desc_lower for word in ["tablet", "capsule", "oral"]):
                types.append("Oral Dosage Form")
            if "injection" in desc_lower:
                types.append("Injectable")
            if "cream" in desc_lower or "ointment" in desc_lower:
                types.append("Topical")
            self.rxnorm_semantic[code] = types

        # SNOMED semantic types
        for code, desc in self.snomed.items():
            desc_lower = desc.lower()
            types = ["Clinical Finding"]
            if any(word in desc_lower for word in ["diabetes", "mellitus"]):
                types.append("Endocrine Disorder")
            if any(word in desc_lower for word in ["hypertension", "hypertensive"]):
                types.append("Cardiovascular Disorder")
            if "asthma" in desc_lower:
                types.append("Respiratory Disorder")
            if "disorder" in desc_lower:
                types.append("Disorder")
            self.snomed_semantic[code] = types

        # LOINC semantic types
        for code, desc in self.loinc.items():
            desc_lower = desc.lower()
            types = ["Laboratory"]
            if any(word in desc_lower for word in ["hemoglobin", "a1c"]):
                types.append("Hematology")
            if "creatinine" in desc_lower:
                types.append("Renal Function")
            if "pressure" in desc_lower:
                types.append("Vital Sign")
            if "calcium" in desc_lower:
                types.append("Electrolyte")
            self.loinc_semantic[code] = types

    def lookup_code(self, code: str, ontology: str) -> str | None:
        """Lookup description by code."""
        if ontology == "icd10":
            return self.icd10.get(code)
        elif ontology == "rxnorm":
            return self.rxnorm.get(code)
        elif ontology == "snomed":
            return self.snomed.get(code)
        elif ontology == "loinc":
            return self.loinc.get(code)
        return None

    def lookup_term(self, term: str, ontology: str) -> str | None:
        """Lookup code by exact term match (case-insensitive)."""
        term_lower = term.lower()
        if ontology == "icd10":
            return self.icd10_rev.get(term_lower)
        elif ontology == "rxnorm":
            return self.rxnorm_rev.get(term_lower)
        elif ontology == "snomed":
            return self.snomed_rev.get(term_lower)
        elif ontology == "loinc":
            return self.loinc_rev.get(term_lower)
        return None

    def get_semantic_types(self, code: str, ontology: str) -> list[str]:
        """Get semantic types for a code to filter false positives."""
        if ontology == "icd10":
            return self.icd10_semantic.get(code, [])
        elif ontology == "rxnorm":
            return self.rxnorm_semantic.get(code, [])
        elif ontology == "snomed":
            return self.snomed_semantic.get(code, [])
        elif ontology == "loinc":
            return self.loinc_semantic.get(code, [])
        return []

    def filter_by_semantic_type(
        self, codes: list[str], ontology: str, allowed_types: list[str]
    ) -> list[str]:
        """Filter codes by allowed semantic types."""
        filtered = []
        for code in codes:
            semantic_types = self.get_semantic_types(code, ontology)
            if any(st in allowed_types for st in semantic_types):
                filtered.append(code)
        return filtered


# Singleton instance placeholder
_loader = None


def get_ontology_loader(repo_root: Path) -> OntologyLoader:
    global _loader
    if _loader is None:
        _loader = OntologyLoader(repo_root / "config/ontologies")
        _loader.load_all()
    return _loader
