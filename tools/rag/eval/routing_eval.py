from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from llmc.routing.router import create_router
from tools.rag.config import load_config
from tools.rag.search import search_spans
from tools.rag.utils import find_repo_root

log = logging.getLogger(__name__)

@dataclass
class EvalResult:
    query_id: str
    query: str
    expected_route: str | None
    predicted_route: str
    route_correct: bool | None
    relevant_slice_ids: list[str]
    retrieved_slice_ids: list[str]
    hit_at_k: bool | None
    rank_of_first_hit: int | None

def evaluate_routing(
    dataset_path: Path, 
    top_k: int = 10, 
    repo_root: Path | None = None
) -> dict[str, Any]:
    
    repo = repo_root or find_repo_root()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
        
    # Load Config & Router
    cfg = load_config(repo)
    router = create_router(cfg)
    
    results: list[EvalResult] = []
    
    with open(dataset_path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.warning(f"Skipping invalid JSON line: {line}")
                continue
                
            query = record.get("query")
            if not query: continue
            
            qid = record.get("id", "unknown")
            expected_route = record.get("expected_route")
            relevant_ids = set(record.get("relevant_slice_ids", []))
            
            # 1. Routing Decision
            decision = router.decide_route(query)
            predicted_route = decision["route_name"]
            
            route_correct = None
            if expected_route:
                route_correct = (predicted_route == expected_route)
                
            # 2. Retrieval
            # We use search_spans which uses the router internally, 
            # but we want to verify the retrieval quality end-to-end.
            # Note: search_spans will re-run routing unless we pass override? 
            # search_spans doesn't take route override. It re-runs routing.
            # That's fine, we are testing the system.
            
            spans = search_spans(query, limit=top_k, repo_root=repo)
            retrieved_ids = [s.span_hash for s in spans]
            
            hit = False
            rank = None
            
            if relevant_ids:
                for i, rid in enumerate(retrieved_ids):
                    if rid in relevant_ids:
                        hit = True
                        rank = i + 1
                        break
            else:
                hit = None # N/A
                
            results.append(EvalResult(
                query_id=qid,
                query=query,
                expected_route=expected_route,
                predicted_route=predicted_route,
                route_correct=route_correct,
                relevant_slice_ids=list(relevant_ids),
                retrieved_slice_ids=retrieved_ids,
                hit_at_k=hit,
                rank_of_first_hit=rank
            ))
            
    # Aggregation
    total = len(results)
    if total == 0:
        return {"error": "No records processed"}
        
    routing_correct_count = sum(1 for r in results if r.route_correct)
    routing_total_evaluated = sum(1 for r in results if r.route_correct is not None)
    
    retrieval_hit_count = sum(1 for r in results if r.hit_at_k)
    retrieval_total_evaluated = sum(1 for r in results if r.hit_at_k is not None)
    
    mrr_sum = 0.0
    for r in results:
        if r.rank_of_first_hit:
            mrr_sum += 1.0 / r.rank_of_first_hit
            
    metrics = {
        "total_examples": total,
        "routing_accuracy": (routing_correct_count / routing_total_evaluated) if routing_total_evaluated else 0.0,
        "retrieval_hit_at_k": (retrieval_hit_count / retrieval_total_evaluated) if retrieval_total_evaluated else 0.0,
        "retrieval_mrr": (mrr_sum / retrieval_total_evaluated) if retrieval_total_evaluated else 0.0
    }
    
    return metrics
