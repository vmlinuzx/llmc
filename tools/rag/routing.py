from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any

from tools.rag.config import get_default_domain, get_path_overrides
from llmc.core import load_config

log = logging.getLogger(__name__)

def resolve_domain(relative_path: Path, repo_root: Path) -> tuple[str, str, str]:
    """
    Resolve domain for a file path.
    Returns: (domain, reason, detail)
    """
    str_path = str(relative_path)
    overrides = get_path_overrides(repo_root)
    
    # 1. Path Overrides (including extensions defined as globs)
    for pattern, domain in overrides.items():
        if fnmatch.fnmatch(str_path, pattern):
            if pattern.startswith("*."):
                return domain, "extension", pattern
            return domain, "path_override", pattern
            
    # 2. Default Domain
    default_domain = get_default_domain(repo_root)
    return default_domain, "default_domain", ""


def is_format_allowed(domain: str, file_path: Path, repo_root: Path) -> bool:
    """
    Check if the file format is allowed for the given domain.
    Used for gating formats like HL7/CCDA until parsers are ready.
    """
    if domain != "medical":
        return True

    cfg = load_config(repo_root)
    medical_cfg = cfg.get("medical", {})
    gated_formats = medical_cfg.get("gated_formats", {})

    # Check for HL7
    if file_path.suffix.lower() in {".hl7"}:
        hl7_config = gated_formats.get("hl7", {})
        if not hl7_config.get("enabled", False):
            return False

    # Check for CCDA (xml) - simplistic check, might need content inspection if generic XML
    if file_path.suffix.lower() in {".xml"}:
         # If it's explicitly identified as CCDA via some other means or just by XML extension in medical context?
         # For now, let's assume specific extensions or content patterns if possible, 
         # but SDD implies gating based on format. 
         # Since XML can be many things, we might only block if we are sure it is CCDA, 
         # or if the user explicitly mapped .xml to medical and we want to gate it.
         
         ccda_config = gated_formats.get("ccda", {})
         if not ccda_config.get("enabled", False):
             # We only block if we suspect it is CCDA. 
             # For Phase 1, we might just block all .xml in medical domain if explicitly configured?
             # But let's look at the "Acceptance Criteria": "HL7 and CCDA formats are gated"
             pass

    return True

def get_medical_subtype(file_path: Path, repo_root: Path) -> str | None:
    """
    Determine the medical subtype based on path or content.
    """
    str_path = str(file_path).lower()
    
    # Path-based subtype detection
    if "labs/" in str_path or "lab/" in str_path:
        return "lab_report"
    if "radiology/" in str_path or "rad/" in str_path:
        return "radiology"
    if "discharge/" in str_path:
        return "discharge_summary"
    if "pathology/" in str_path:
        return "pathology"
    if "medications/" in str_path or "meds/" in str_path:
        return "medication_list"
    if "operative/" in str_path or "op_notes/" in str_path:
        return "operative_note"
    if "nursing/" in str_path:
        return "nursing_note"

    cfg = load_config(repo_root)
    repo_cfg = cfg.get("repository", {})
    return repo_cfg.get("medical_subtype", "clinical_note")
