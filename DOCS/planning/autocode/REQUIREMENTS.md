# REQUIREMENTS: Domain RAG Tech Docs — Phase 6

**SDD Source:** `DOCS/planning/SDD_Domain_RAG_Tech_Docs.md` → Section 7, Phase 6
**Branch:** `feature/domain-rag-tech-docs`
**Scope:** Extended Evaluation — nDCG and Golden Query Sets

---

## Objective

Implement graded relevance metrics (nDCG) and establish a golden query set for ongoing quality evaluation.

---

## Acceptance Criteria

### AC-1: nDCG Metric Implementation

**Add to `tools/rag/metrics/retrieval.py`:**

```python
def ndcg_at_k(results: list[list[float]], k: int = 10) -> float:
    """Calculate nDCG@K across queries.
    
    Args:
        results: List of result lists, where value is relevance score (0.0 to 1.0+)
        k: Number of results to consider
        
    Returns:
        nDCG@K score (0.0 to 1.0)
    """
    # ... implementation ...
```

**Tests:** `tests/rag/test_retrieval_metrics.py`
- `test_ndcg_at_k_perfect()` — Perfect ordering = 1.0
- `test_ndcg_at_k_worst()` — Worst ordering < 1.0
- `test_ndcg_at_k_empty()` — Empty results = 0.0

### AC-2: Golden Query Set Schema & Loader

**Create `tools/rag/eval/query_set.py`:**

```python
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
    # Load and validate JSON
    pass
```

**Tests:** `tests/rag/eval/test_query_set.py`
- `test_load_valid_set()`
- `test_schema_validation()`

### AC-3: Tech Docs Golden Query Set

**Create `tests/eval/tech_docs_queries.json`:**
- Create a sample golden set with at least 3 queries relevant to LLMC tech docs (e.g., "how to configure enrichment", "install mcp").
- Include graded relevance judgments (0, 1, 2).

---

## Out of Scope (End of SDD)

- ❌ Automated judgment generation (LLM-as-a-Judge) - Future R&D
- ❌ UI for query labeling

---

## Verification

B-Team must verify:
1. `tools/rag/metrics/retrieval.py` has `ndcg_at_k`.
2. `tools/rag/eval/query_set.py` exists and validates schema.
3. `tests/eval/tech_docs_queries.json` exists with valid data.
4. New tests pass.

---

**END OF REQUIREMENTS**