"""
Ontology Loaders and Lookup.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any

class OntologyLoader:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.icd10 = {}
        self.rxnorm = {}
        self.snomed = {}
        self.loinc = {}
        
    def load_all(self):
        """Load all ontologies from JSON files."""
        self.icd10 = self._load_json("icd10cm_2024.json")
        self.rxnorm = self._load_json("rxnorm_2024.json")
        self.snomed = self._load_json("snomed_us_2024.json")
        self.loinc = self._load_json("loinc_2024.json")
        
        # Build reverse lookups (Term -> Code) for simple matching
        self.icd10_rev = {v.lower(): k for k, v in self.icd10.items()}
        self.rxnorm_rev = {v.lower(): k for k, v in self.rxnorm.items()}
        self.snomed_rev = {v.lower(): k for k, v in self.snomed.items()}
        self.loinc_rev = {v.lower(): k for k, v in self.loinc.items()}

    def _load_json(self, filename: str) -> Dict[str, str]:
        p = self.config_dir / filename
        if p.exists():
            try:
                with open(p, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def lookup_code(self, code: str, ontology: str) -> Optional[str]:
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

    def lookup_term(self, term: str, ontology: str) -> Optional[str]:
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

# Singleton instance placeholder
_loader = None

def get_ontology_loader(repo_root: Path) -> OntologyLoader:
    global _loader
    if _loader is None:
        _loader = OntologyLoader(repo_root / "config/ontologies")
        _loader.load_all()
    return _loader
