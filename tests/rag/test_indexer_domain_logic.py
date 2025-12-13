
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tools.rag import indexer

@patch("tools.rag.indexer.iter_source_files")
@patch("tools.rag.indexer.find_repo_root")
@patch("tools.rag.indexer.Database")
@patch("tools.rag.indexer.classify_slice")
@patch("tools.rag.indexer.extract_spans")
@patch("tools.rag.indexer.populate_span_hashes")
@patch("tools.rag.indexer.build_file_record")
@patch("tools.rag.indexer.ensure_storage")
@patch("tools.rag.indexer.index_path_for_write")
@patch("tools.rag.indexer.resolve_spans_export_path")
@patch("tools.rag.indexer.get_path_overrides")
@patch("tools.rag.indexer.get_default_domain")
def test_index_repo_domain_logging(
    mock_get_default_domain,
    mock_get_path_overrides,
    mock_resolve_spans,
    mock_index_path,
    mock_ensure_storage,
    mock_build_record,
    mock_populate_hashes,
    mock_extract_spans,
    mock_classify,
    mock_db,
    mock_find_root,
    mock_iter_files,
    capsys,
    caplog
):
    # Setup
    mock_root = Path("/tmp/mock_repo")
    mock_find_root.return_value = mock_root
    # mock_root.name = "mock_repo" # Removed
    
    # Mock files
    mock_iter_files.return_value = [Path("DOCS/API.md"), Path("src/main.py")]
    
    # Mock config
    mock_get_default_domain.return_value = "tech_docs"
    mock_get_path_overrides.return_value = {
        "DOCS/**": "tech_docs",
        "*.py": "code"
    }
    
    # Mock file reading (absolute path)
    with patch("pathlib.Path.read_bytes", return_value=b"content") as mock_read:
        with patch("pathlib.Path.stat") as mock_stat:
             mock_stat.return_value.st_size = 100
             mock_stat.return_value.st_mtime = 1000.0
             
             # Mock DB
             db_instance = mock_db.return_value
             db_instance.get_file_hash.return_value = "old_hash" # Force update

             # Mock extract
             mock_extract_spans.return_value = [MagicMock()]

             # Run index_repo with flag
             with caplog.at_level(logging.INFO):
                 indexer.index_repo(show_domain_decisions=True, export_json=False)

    # Verify Output (AC-3)
    captured = capsys.readouterr()
    stdout = captured.out
    
    assert "INFO indexer: file=DOCS/API.md domain=tech_docs reason=path_override:DOCS/**" in stdout
    assert "INFO indexer: file=src/main.py domain=code reason=extension:*.py" in stdout

    # Verify Logs (AC-2)
    # Check for structured logs in captured logs
    found_docs_log = False
    found_code_log = False
    
    for record in caplog.records:
        if "domain=tech_docs" in record.message and "override=\"DOCS/**\"" in record.message:
            found_docs_log = True
        if "domain=code" in record.message and "override=\"*.py\"" in record.message:
            found_code_log = True
            
    assert found_docs_log, "Missing AC-2 log for DOCS/API.md"
    assert found_code_log, "Missing AC-2 log for src/main.py"
