from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class ClassificationResult:
    slice_type: str
    slice_language: str | None
    confidence: float
    reasons: list[str]
    classifier_version: str = "v1.0"


# Extension mappings
EXT_TYPE_MAP = {
    # code
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".tsx": "code",
    ".jsx": "code",
    ".c": "code",
    ".h": "code",
    ".cpp": "code",
    ".hpp": "code",
    ".java": "code",
    ".go": "code",
    ".rs": "code",
    ".cs": "code",
    ".php": "code",
    ".rb": "code",
    ".kt": "code",
    ".swift": "code",
    # config
    ".yml": "config",
    ".yaml": "config",
    ".toml": "config",
    ".ini": "config",
    ".cfg": "config",
    ".json": "config",
    ".xml": "config",
    # docs
    ".md": "docs",
    ".rst": "docs",
    ".txt": "docs",
    ".adoc": "docs",
    # data
    ".csv": "data",
    ".tsv": "data",
}

# Language mapping (subset of EXT_TYPE_MAP for code)
EXT_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".swift": "swift",
}

SHEBANG_REGEX = re.compile(r"^#!.*(python|bash|sh|node|env python|env bash)")
ERP_KEY_REGEX = re.compile(
    r'["\']?(sku|upc|asin|model_number|product_id|catalog_ref)["\']?\s*[:=]', re.IGNORECASE
)


def classify_slice(path: Path, mime: str | None, text: str) -> ClassificationResult:
    reasons = []
    confidence = 0.0
    slice_type = "other"
    slice_language = None

    # 0. ERP/Product check (High priority)
    # Path heuristics
    str(path).lower()
    is_erp_path = any(part in path.parts for part in ["erp", "pim", "products", "catalog"])

    # Content heuristics for structured files
    is_structured_ext = path.suffix.lower() in [".json", ".yaml", ".yml", ".csv", ".xml"]
    has_erp_keys = False
    if is_structured_ext and text:
        # Scan first 2k chars for speed
        sample = text[:2000]
        if ERP_KEY_REGEX.search(sample):
            has_erp_keys = True

    if is_erp_path or (is_structured_ext and has_erp_keys):
        return ClassificationResult(
            slice_type="erp_product",
            slice_language=None,  # data usually doesn't have a language
            confidence=1.0 if is_erp_path and has_erp_keys else 0.8,
            reasons=["erp path" if is_erp_path else "erp keys"],
        )

    # 1. Extension check
    ext = path.suffix.lower()
    if ext in EXT_TYPE_MAP:
        slice_type = EXT_TYPE_MAP[ext]
        reasons.append(f"extension {ext}")
        confidence = 1.0

        if ext in EXT_LANG_MAP:
            slice_language = EXT_LANG_MAP[ext]

    # 2. Shebang check (override extension if it looks like a script)
    # Only check first line
    first_line = ""
    if text:
        try:
            first_line = text.splitlines()[0]
        except IndexError:
            pass

    if first_line.startswith("#!"):
        match = SHEBANG_REGEX.match(first_line)
        if match:
            slice_type = "code"
            reasons.append(f"shebang {match.group(0)}")
            confidence = 1.0
            # Try to infer language from shebang
            shebang_content = match.group(1)
            if "python" in shebang_content:
                slice_language = "python"
            elif "node" in shebang_content:
                slice_language = "javascript"  # assumption
            elif "bash" in shebang_content or "sh" in shebang_content:
                slice_language = "shell"

    return ClassificationResult(
        slice_type=slice_type, slice_language=slice_language, confidence=confidence, reasons=reasons
    )
