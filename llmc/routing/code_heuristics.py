from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .common import RouteSignal

FENCE_OPEN_RE = re.compile(r'(^|[\s:,\(\)\{\}\[\]])```[\w-]*\s*\n', re.MULTILINE)

def count_fenced_code_blocks(text: str) -> int:
    count = 0
    pos = 0
    while True:
        m = FENCE_OPEN_RE.search(text, pos)
        if not m:
            break
        open_idx = m.end()
        close_idx = text.find("```", open_idx)
        if close_idx != -1:
            count += 1
            pos = close_idx + 3
        else:
            break
    return count

def has_fenced_code(text: str) -> bool:
    return count_fenced_code_blocks(text) >= 1

# Regexes with non-capturing groups for anchors
CODE_STRUCT_REGEXES = [
    re.compile(r"(?:^|\n)\s*(def|async\s+def|class)\s+\w+", re.MULTILINE),
    re.compile(r"(?:^|\n)\s*from\s+\w+", re.MULTILINE),
    re.compile(r"(?:^|\n)\s*import\s+\w+", re.MULTILINE),
    re.compile(r"(?:^|\n)\s*\w+\s*=\s*[^=\n]+", re.MULTILINE),
    re.compile(r"\bfor\s+\w+\s+in\s+[^:\n]+:?\s*", re.MULTILINE),
    re.compile(r"\bwhile\s+[^:\n]+:?\s*", re.MULTILINE),
    re.compile(r"\blambda\s+\w+\s*:\s*[^:\n]+", re.MULTILINE),
    re.compile(r"\b\w+\s*\([^()\n]*\)", re.MULTILINE),
]

CODE_KEYWORDS = {
    "if","elif","else","for","while","return","def","class","import","from",
    "try","except","with","lambda","yield","self","cls","print",
    "function","var","const","let","console.log","=>","async","await",
    "args","kwargs","dict","list","tuple","int","str","bool","None",
}

def score_all(text: str, cfg: Dict[str, Any] | None = None) -> RouteSignal | None:
    # 1. Fences
    if has_fenced_code(text):
        return RouteSignal(route="code", score=0.95, reason="heuristic=fenced-code")
    
    # 2. Structure
    matches = []
    for regex in CODE_STRUCT_REGEXES:
        found = regex.findall(text)
        for f in found:
            s = f[0] if isinstance(f, tuple) else f
            if s.strip():
                matches.append(s.strip())
                if len(matches) >= 3: break
        if len(matches) >= 3: break
    
    if matches:
        return RouteSignal(route="code", score=0.85, reason=f"code-structure={','.join(matches[:3])}")

    # 3. Keywords
    # Use word boundaries to avoid substring false positives (e.g. "shift" -> "if")
    words = set(re.findall(r"\b\w+\b", text))
    found = words.intersection(CODE_KEYWORDS)
    
    if len(found) >= 1:
        # Score: 0.8 for 2+ keywords (Tie with ERP), 0.4 for 1 (Weaker)
        score = 0.8 if len(found) >= 2 else 0.4
        return RouteSignal(route="code", score=score, reason=f"code-keywords={','.join(list(found)[:3])}")

    return None