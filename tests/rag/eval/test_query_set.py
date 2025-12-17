import json

from pydantic import ValidationError
import pytest

from llmc.rag.eval.query_set import load_query_set


def test_load_valid_set(tmp_path):
    data = {
        "version": "1.0",
        "queries": [
            {
                "query_id": "q1",
                "text": "test query",
                "judgments": [
                    {"doc_id": "doc1", "score": 1.0}
                ]
            }
        ]
    }
    f = tmp_path / "valid.json"
    f.write_text(json.dumps(data))
    
    qs = load_query_set(str(f))
    assert qs.version == "1.0"
    assert len(qs.queries) == 1
    assert qs.queries[0].text == "test query"

def test_schema_validation(tmp_path):
    data = {
        "version": "1.0",
        "queries": [
            {
                "query_id": "q1",
                # Missing text
                "judgments": []
            }
        ]
    }
    f = tmp_path / "invalid.json"
    f.write_text(json.dumps(data))
    
    with pytest.raises(ValidationError):
        load_query_set(str(f))

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_query_set("non_existent_file.json")
