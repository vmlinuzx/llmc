"""
Main Medical Extractor Module.
Orchestrates segmentation and entity extraction.
"""

from typing import List, Dict, Any, Optional
import re
from .medical_segmenter import segment_note, Segment
from .medical_abbreviations import expand_abbreviation

# Try to import heavy NLP libs, fall back to stubs
try:
    import spacy
    import scispacy
    from medspacy.context import ConTextComponent
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


class MedicalExtractor:
    def __init__(self):
        self.nlp = None
        if NLP_AVAILABLE:
            try:
                # Load a lightweight model or default
                self.nlp = spacy.load("en_core_sci_sm") # Assumption: installed if NLP_AVAILABLE
            except Exception:
                pass 
                
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Main entry point for extracting data from a clinical note.
        """
        segments = segment_note(text)
        
        extracted_data = {
            "sections": [],
            "medications": [],
            "labs": [],
            "diagnoses": []
        }
        
        for seg in segments:
            section_data = {
                "type": seg.section_type,
                "content": seg.content,
                "start_line": seg.start_line,
                "end_line": seg.end_line
            }
            extracted_data["sections"].append(section_data)
            
            # Extract entities based on section type
            if seg.section_type == "medications":
                meds = self._extract_meds(seg.content)
                extracted_data["medications"].extend(meds)
                
            if seg.section_type == "labs":
                labs = self._extract_labs(seg.content)
                extracted_data["labs"].extend(labs)
                
            if seg.section_type == "assessment" or seg.section_type == "impression":
                diags = self._extract_diagnoses(seg.content)
                extracted_data["diagnoses"].extend(diags)

        return extracted_data

    def _extract_meds(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract medications using regex (fallback) or NLP.
        """
        meds = []
        # Simple regex for MVP: "Name 10mg PO BID"
        # Matches: Name (alpha), Dose (digit+unit), Route (PO/IV), Freq (BID/QD)
        # This is very basic and brittle, strictly for MVP/Stub
        lines = text.splitlines()
        for line in lines:
            if not line.strip(): continue
            
            # Heuristic: if line looks like a med listing
            # Example: "Lisinopril 10mg PO Daily"
            parts = line.split()
            if len(parts) >= 2:
                # Very naive parsing
                name = parts[0]
                # Check if it looks like a drug (not a common word?) - skipped for MVP
                
                meds.append({
                    "name": name,
                    "raw": line.strip(),
                    "source": "regex_fallback"
                })
        return meds

    def _extract_labs(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract labs using pattern matching line-by-line.
        Example: "Hgb 12.5", "Na 140", "K 4.0"
        """
        labs = []
        # Pattern: Key Value [Unit]
        # e.g. "Hgb: 14.0 g/dL" or "Hgb 14.0"
        # Anchored to avoid matching mid-sentence noise if possible, or just strict structure
        pattern = re.compile(r"^\s*([A-Za-z]+)[:\s]+(\d+(?:\.\d+)?)(?:\s+([A-Za-z/%]+))?\s*$")
        
        lines = text.splitlines()
        for line in lines:
            if not line.strip(): continue
            match = pattern.search(line)
            if match:
                key, val, unit = match.groups()
                if key.lower() in ["am", "pm"]: continue # False positive time
                
                labs.append({
                    "key": key,
                    "value": float(val),
                    "unit": unit or "",
                    "abnormal": None # Logic deferred
                })
        return labs

    def _extract_diagnoses(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract diagnoses.
        """
        diags = []
        # For MVP, assume one diagnosis per line in Assessment
        lines = text.splitlines()
        for line in lines:
            clean = line.strip("- ").strip()
            if clean:
                diags.append({
                    "term": clean,
                    "context": {} # Default
                })
        return diags
