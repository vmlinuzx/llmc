from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Common code patterns
# Ends with semicolon, curly braces, parens, brackets
CODE_STRUCT_REGEX = re.compile(r"(\n\s*[\}\]\)];|\{|\}|=>|->|public static|fn |func |def |class |#include)", re.MULTILINE)
# Keywords (simple heuristic)
CODE_KEYWORDS = {"def", "class", "return", "import", "from", "var", "let", "const", "function", "if", "for", "while", "switch", "case", "break", "continue"}

def classify_query(text: str, tool_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a deterministic classification for a query.

    Returns:
        {
            "route_name": "code" | "docs",
            "confidence": float,  # 0.0 - 1.0
            "reasons": list[str], # human-readable reasons for logging
        }
    """
    reasons: List[str] = []
    route_name = "docs"
    confidence = 0.5
    
    # 1. Tool/context hint (highest priority)
    if tool_context:
        tool_id = str(tool_context.get("tool_id", "")).lower()
        # Code-oriented tools
        if any(x in tool_id for x in ["code", "refactor", "nav", "search_code", "ast"]):
            return {
                "route_name": "code",
                "confidence": 1.0,
                "reasons": [f"tool_context={tool_id}"]
            }
        # ERP/Product lookup
        if "erp" in tool_id or "product" in tool_id:
            return {
                "route_name": "docs",
                "confidence": 1.0,
                "reasons": [f"tool_context={tool_id}"]
            }

    # 2. Code-like text detection
    text_stripped = text.strip()
    
    # Code fences check
    if "```" in text:
        # If it has code fences, it's likely referring to code or asking about code
        # We'll treat it as code if it has language hints inside, or just generally strongly imply code
        return {
            "route_name": "code",
            "confidence": 0.9,
            "reasons": ["heuristic=code_fences"]
        }

    # Structure check
    structure_matches = CODE_STRUCT_REGEX.findall(text)
    if len(structure_matches) > 0:
        reasons.append(f"pattern={','.join(set(structure_matches[:3]))}")
        route_name = "code"
        confidence = 0.7

    # Keyword density check
    words = set(re.findall(r"\b\w+\b", text))
    code_keywords_found = words.intersection(CODE_KEYWORDS)
    if len(code_keywords_found) >= 2:
        reasons.append(f"keywords={','.join(list(code_keywords_found)[:3])}")
        route_name = "code"
        # Boost confidence if we already matched structure, otherwise set it
        confidence = 0.8 if route_name == "code" else 0.7

    # If no strong code signals, default to docs
    if route_name == "docs":
        reasons.append("default=docs")

    return {
        "route_name": route_name,
        "confidence": confidence,
        "reasons": reasons
    }
