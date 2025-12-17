from __future__ import annotations

import re
from typing import Any

from .common import RouteSignal

ERP_SKU_RE = re.compile(r"\b([A-Z]{1,4}-\d{4,6})\b")
ERP_WORDS = {
    "sku",
    "upc",
    "asin",
    "model",
    "model number",
    "item",
    "product",
    "catalog",
    "inventory",
    "price",
    "stock",
    "order",
    "invoice",
    "po",
    "so",
}


def score_all(text: str, cfg: dict[str, Any] | None = None) -> RouteSignal | None:
    tl = text.lower()
    m = ERP_SKU_RE.search(text)
    if m:
        return RouteSignal(route="erp", score=0.85, reason=f"erp:sku={m.group(1)}")
    hits = [w for w in ERP_WORDS if w in tl]
    if len(hits) >= 2:
        return RouteSignal(
            route="erp", score=0.70, reason=f"erp:kw2={','.join(hits[:3])}"
        )
    if len(hits) == 1:
        return RouteSignal(route="erp", score=0.55, reason=f"erp:kw1={hits[0]}")
    return None
