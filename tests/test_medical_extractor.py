"""
Tests for Phase 2 Medical Extractor.
"""
import pytest
from textwrap import dedent
from llmc.rag.extractors.medical_segmenter import segment_note, Segment
from llmc.rag.extractors.medical_headers import normalize_header
from llmc.rag.extractors.medical_abbreviations import expand_abbreviation
from llmc.rag.extractors.medical import MedicalExtractor

def test_header_normalization():
    assert normalize_header("History of Present Illness") == "subjective"
    assert normalize_header("HPI") == "subjective"
    assert normalize_header("MEDICATIONS") == "medications"
    assert normalize_header("Assessment and Plan") == "assessment"
    assert normalize_header("Unknown Header") is None

def test_abbreviation_expansion():
    assert expand_abbreviation("htn") == "hypertension"
    assert expand_abbreviation("HTN") == "hypertension"
    assert expand_abbreviation("bid") == "twice a day"
    assert expand_abbreviation("unknown") == "unknown"

def test_segmentation_simple():
    note = dedent("""
    History of Present Illness:
    Patient is a 50yo male.
    
    Medications:
    Aspirin 81mg
    
    Assessment:
    Hypertension.
    """).strip()
    segments = segment_note(note)
    assert len(segments) == 3
    assert segments[0].section_type == "subjective"
    assert "Patient is a 50yo male" in segments[0].content
    assert segments[1].section_type == "medications"
    assert "Aspirin 81mg" in segments[1].content
    assert segments[2].section_type == "assessment"

def test_extractor_integration():
    note = dedent("""
    History of Present Illness:
    Patient feels fine.
    
    Labs:
    Hgb 14.0
    Na 140
    
    Assessment:
    1. Hypertension
    2. Diabetes
    """).strip()
    extractor = MedicalExtractor()
    result = extractor.extract(note)
    
    assert len(result["sections"]) == 3
    
    # Check Labs
    labs = result["labs"]
    assert len(labs) >= 2
    assert labs[0]["key"] == "Hgb"
    assert labs[0]["value"] == 14.0
    
    # Check Diagnoses
    diags = result["diagnoses"]
    assert len(diags) >= 2
    assert "Hypertension" in diags[0]["term"]
