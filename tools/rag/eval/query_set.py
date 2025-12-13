import json
from pathlib import Path

from pydantic import BaseModel


class RelevanceJudgment(BaseModel):
    doc_id: str
    score: float  # 0.0=irrelevant, 1.0=relevant, 2.0=highly relevant

class EvalQuery(BaseModel):
    query_id: str
    text: str
    judgments: list[RelevanceJudgment]

class GoldenQuerySet(BaseModel):
    version: str
    queries: list[EvalQuery]

def load_query_set(path: str) -> GoldenQuerySet:
    """Load and validate a GoldenQuerySet from a JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Query set file not found: {path}")
    
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
        
    return GoldenQuerySet(**data)
