from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class RouteSignal:
    route: str
    score: float
    reason: str

# Common code patterns
CODE_STRUCT_REGEXES = [
    re.compile(r"(?:^|\n)\s*(def|async\s+def|class)\s+\w+", re.MULTILINE),  # defs/classes
    re.compile(r"(?:^|\n)\s*from\s+\w+", re.MULTILINE),                      # from x import y
    re.compile(r"(?:^|\n)\s*import\s+\w+", re.MULTILINE),                    # import x
    re.compile(r"(?:^|\n)\s*\w+\s*=\s*[^=\n]+", re.MULTILINE),               # assignment (not ==)
    re.compile(r"\bfor\s+\w+\s+in\s+[^:\n]+:?\s*", re.MULTILINE),          # for-loops
    re.compile(r"\bwhile\s+[^:\n]+:?\s*", re.MULTILINE),                   # while-loops
    re.compile(r"\blambda\s+\w+\s*:\s*[^:\n]+", re.MULTILINE),             # lambda
    re.compile(r"\b\w+\s*\([^()\n]*\)", re.MULTILINE),                     # simple function call foo(...)
]

# Keywords (Expanded for Phase 2)
CODE_KEYWORDS = {
    # Python
    "if","elif","else","for","while","return","def","class","import","from",
    "try","except","with","lambda","yield","self","cls","print",
    # JS / generic
    "function","var","const","let","console.log","=>","async","await",
    # Common code nouns
    "args","kwargs","dict","list","tuple","int","str","bool","None",
}

# ERP Patterns
ERP_SKU_REGEX = re.compile(r"\b([A-Z]{1,4}-\d{4,6})\b") # Matches W-44910, STR-66320
ERP_KEYWORDS = {"sku", "upc", "asin", "model number", "item", "product", "catalog", "inventory", "price", "stock"}

# Phase 1 – Change 3: Minimal but more robust fenced code detection
FENCE_OPEN_RE = re.compile(r'(^|\n)```[\w-]*\s*\n', re.MULTILINE)

def _count_fenced_code_blocks(_s: str) -> int:
    """Count fenced code blocks like: ```lang(optional)\n...\n```
    Returns number of complete fenced blocks (open + close).
    """
    count = 0
    pos = 0
    while True:
        m = FENCE_OPEN_RE.search(_s, pos)
        if not m:
            break
        open_idx = m.end()
        close_idx = _s.find("```", open_idx)
        if close_idx != -1:
            count += 1
            pos = close_idx + 3
        else:
            # no closing fence; stop scanning
            break
    return count

def score_code_fences(text: str) -> Optional[RouteSignal]:
    if _count_fenced_code_blocks(text) >= 1:
        return RouteSignal(route="code", score=0.9, reason="heuristic=fenced-code")
    return None

def score_code_structure(text: str) -> Optional[RouteSignal]:
    matches = []
    for regex in CODE_STRUCT_REGEXES:
        found = regex.findall(text)
        for f in found:
            # regex might return tuple (groups) or string
            s = f[0] if isinstance(f, tuple) else f
            if s.strip():
                matches.append(s.strip())
                if len(matches) >= 3: break
        if len(matches) >= 3: break
            
    if matches:
        # Score boosts slightly with more matches, capped at 0.85
        base_score = 0.8
        return RouteSignal(route="code", score=base_score, reason=f"code-structure={','.join(matches[:3])}")
    return None

def score_code_keywords(text: str) -> Optional[RouteSignal]:
    words = set(re.findall(r"\b\w+\b", text))
    found = words.intersection(CODE_KEYWORDS)
    
    # Phase 2: Lower threshold to >= 1 keyword, but lower confidence
    if len(found) >= 1:
        # Score: 0.8 for 2+ keywords (Tie with ERP), 0.4 for 1 (Weaker)
        score = 0.8 if len(found) >= 2 else 0.4
        return RouteSignal(route="code", score=score, reason=f"code-keywords={','.join(list(found)[:3])}")
    return None

def _score_erp(text: str, text_lower: str) -> Optional[RouteSignal]:
    sku_matches = ERP_SKU_REGEX.findall(text)
    if sku_matches:
        return RouteSignal(route="erp", score=0.9, reason=f"sku_pattern={','.join(sku_matches[:3])}")
        
    erp_kw_found = [w for w in ERP_KEYWORDS if w in text_lower]
    if len(erp_kw_found) >= 2 or ("sku" in erp_kw_found and len(erp_kw_found) >= 1):
        return RouteSignal(route="erp", score=0.8, reason=f"erp_keywords={','.join(erp_kw_found[:3])}")
    return None

def classify_query(text: str, tool_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a deterministic classification for a query.

    Returns:
        {
            "route_name": "code" | "docs" | "erp",
            "confidence": float,  # 0.0 - 1.0
            "reasons": list[str], # human-readable reasons for logging
        }
    """
    # Normalize input (Phase 1 – Change 1)
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        return {
            "route_name": "docs",
            "confidence": 0.2,
            "reasons": ["empty-or-none-input"]
        }

    # 1. Tool/context hint (highest priority)
    if tool_context:
        tool_id = str(tool_context.get("tool_id", "")).lower()
        if any(x in tool_id for x in ["erp", "product", "inventory", "sku"]):
            return {"route_name": "erp", "confidence": 1.0, "reasons": [f"tool_context={tool_id}"]}
        if any(x in tool_id for x in ["code", "refactor", "nav", "search_code", "ast"]):
            return {"route_name": "code", "confidence": 1.0, "reasons": [f"tool_context={tool_id}"]}

    text_lower = text.lower()
    
    # Collect Signals
    signals: List[RouteSignal] = []
    
    # Code Signals
    if s := score_code_fences(text): signals.append(s)
    if s := score_code_structure(text): signals.append(s)
    if s := score_code_keywords(text): signals.append(s)
    
    # ERP Signal
    erp_signal = _score_erp(text, text_lower)
    if erp_signal:
        signals.append(erp_signal)
    
    # Select Best Signal
    if not signals:
        return {
            "route_name": "docs",
            "confidence": 0.5,
            "reasons": ["default=docs"]
        }
    
    # Phase 3: Conflict Resolution with Configurable Policy
    # Default config: Prefer Code if score is within margin of ERP
    PREFER_CODE = True
    CONFLICT_MARGIN = 0.1

    code_signals = [s for s in signals if s.route == "code"]
    erp_signals = [s for s in signals if s.route == "erp"]
    
    best_code = max(code_signals, key=lambda x: x.score) if code_signals else None
    best_erp = max(erp_signals, key=lambda x: x.score) if erp_signals else None
    
    selected_signal = signals[0] # Default fallback (should be overwritten)
    
    if best_code and not best_erp:
        selected_signal = best_code
    elif best_erp and not best_code:
        selected_signal = best_erp
    elif best_code and best_erp:
        # Conflict detected
        if PREFER_CODE:
            # If Code score is high enough relative to ERP (within margin), prefer Code.
            # e.g. Code=0.8, ERP=0.9, Margin=0.1 -> 0.8 >= 0.8 -> Code wins.
            if best_code.score >= (best_erp.score - CONFLICT_MARGIN):
                selected_signal = best_code
            else:
                selected_signal = best_erp
        else:
            # Strict score comparison
            if best_code.score >= best_erp.score:
                selected_signal = best_code
            else:
                selected_signal = best_erp
    else:
        # Should be unreachable if signals is not empty
        selected_signal = max(signals, key=lambda x: x.score)

    return {
        "route_name": selected_signal.route,
        "confidence": selected_signal.score,
        "reasons": [s.reason for s in signals]
    }