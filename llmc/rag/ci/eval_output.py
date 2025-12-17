import json
from pathlib import Path


def generate_eval_artifact(
    mrr: float,
    recall_at_10: float,
    output_path: Path
) -> None:
    """Generate tech_docs_eval.json artifact."""
    artifact = {
        "version": "1.0",
        "metrics": {
            "mrr": mrr,
            "recall_at_10": recall_at_10
        },
        "thresholds": {
            "recall_at_10_target": 0.9
        },
        "passed": recall_at_10 >= 0.9
    }
    output_path.write_text(json.dumps(artifact, indent=2))
