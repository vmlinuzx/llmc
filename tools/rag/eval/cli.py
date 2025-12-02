import argparse
import json
from pathlib import Path
import sys

from tools.rag.eval.routing_eval import evaluate_routing


def main():
    parser = argparse.ArgumentParser(description="LLMC Routing Evaluation")
    parser.add_argument("--dataset", type=str, required=True, help="Path to JSONL dataset")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to retrieve")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    try:
        metrics = evaluate_routing(Path(args.dataset), top_k=args.top_k)
        
        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print("=== Routing Evaluation Results ===")
            print(f"Total Examples:     {metrics['total_examples']}")
            print(f"Routing Accuracy:   {metrics['routing_accuracy']:.2%}")
            print(f"Retrieval Hit@{args.top_k}:    {metrics['retrieval_hit_at_k']:.2%}")
            print(f"Retrieval MRR:      {metrics['retrieval_mrr']:.4f}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
