import json

from llmc.rag.ci.eval_output import generate_eval_artifact


def test_generate_artifact(tmp_path) -> None:
    """Creates valid JSON file"""
    output_path = tmp_path / "tech_docs_eval.json"
    generate_eval_artifact(0.8, 0.95, output_path)

    assert output_path.exists()
    content = json.loads(output_path.read_text())
    assert content["version"] == "1.0"


def test_artifact_contains_metrics(tmp_path) -> None:
    """Contains mrr and recall_at_10"""
    output_path = tmp_path / "tech_docs_eval.json"
    generate_eval_artifact(0.75, 0.85, output_path)

    content = json.loads(output_path.read_text())
    assert content["metrics"]["mrr"] == 0.75
    assert content["metrics"]["recall_at_10"] == 0.85


def test_passed_flag_success(tmp_path) -> None:
    """passed=True when recall >= 0.9"""
    output_path = tmp_path / "tech_docs_eval.json"
    generate_eval_artifact(0.8, 0.9, output_path)

    content = json.loads(output_path.read_text())
    assert content["passed"] is True


def test_passed_flag_failure(tmp_path) -> None:
    """passed=False when recall < 0.9"""
    output_path = tmp_path / "tech_docs_eval.json"
    generate_eval_artifact(0.8, 0.89, output_path)

    content = json.loads(output_path.read_text())
    assert content["passed"] is False
