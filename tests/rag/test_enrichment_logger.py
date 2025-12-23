"""Tests for enrichment_logger.py — JSONL logging and ledger repair."""

import json
from pathlib import Path

from llmc.rag.enrichment_logger import EnrichmentLogger, repair_ledger


class TestEnrichmentLogger:
    """Test EnrichmentLogger JSONL output."""

    def test_log_success_creates_jsonl_entry(self, tmp_path: Path):
        """Test that log_success creates a valid JSONL entry."""
        logger = EnrichmentLogger(tmp_path)
        
        logger.log_success(
            span_hash="abc123",
            file_path="src/main.py",
            start_line=10,
            end_line=20,
            duration_sec=2.5,
            model="qwen3:4b",
            meta={"tokens_per_second": 45.2},
        )
        
        ledger = tmp_path / "run_ledger.jsonl"
        assert ledger.exists(), "Ledger file should be created"
        
        line = ledger.read_text().strip()
        entry = json.loads(line)
        
        assert entry["span_hash"] == "abc123"
        assert entry["path"] == "src/main.py"
        assert entry["lines"] == [10, 20]
        assert entry["success"] is True
        assert entry["model"] == "qwen3:4b"
        assert "timestamp" in entry

    def test_log_failure_creates_jsonl_entry(self, tmp_path: Path):
        """Test that log_failure creates a valid JSONL entry with error."""
        logger = EnrichmentLogger(tmp_path)
        
        logger.log_failure(
            span_hash="def456",
            file_path="src/bad.py",
            start_line=1,
            end_line=5,
            duration_sec=0.5,
            error="Connection timeout",
        )
        
        ledger = tmp_path / "run_ledger.jsonl"
        line = ledger.read_text().strip()
        entry = json.loads(line)
        
        assert entry["success"] is False
        assert "timeout" in entry["error"].lower()

    def test_ledger_uses_jsonl_extension(self, tmp_path: Path):
        """Test that ledger file uses .jsonl extension (not .log)."""
        logger = EnrichmentLogger(tmp_path)
        assert logger._ledger_path.suffix == ".jsonl"
        assert "run_ledger.jsonl" in str(logger._ledger_path)


class TestRepairLedger:
    """Test repair_ledger corrupt file handling."""

    def test_repair_ledger_handles_corrupt_lines(self, tmp_path: Path):
        """Test that corrupt lines are discarded and valid lines preserved."""
        ledger = tmp_path / "test_ledger.jsonl"
        
        # Create file with mix of valid and corrupt lines
        ledger.write_text(
            '{"valid": true, "id": 1}\n'
            'this is not json\n'
            '{"valid": true, "id": 2}\n'
            'another corrupt line\n'
            '{"valid": true, "id": 3}\n'
        )
        
        valid, discarded = repair_ledger(ledger)
        
        assert valid == 3, f"Expected 3 valid lines, got {valid}"
        assert discarded == 2, f"Expected 2 discarded lines, got {discarded}"

    def test_repair_ledger_creates_backup(self, tmp_path: Path):
        """Test that original file is backed up when corruption found."""
        ledger = tmp_path / "test_ledger.jsonl"
        
        ledger.write_text(
            '{"valid": true}\n'
            'corrupt\n'
        )
        
        repair_ledger(ledger)
        
        # Note: repair_ledger uses .log.bak suffix regardless of original extension
        backup = tmp_path / "test_ledger.log.bak"
        assert backup.exists(), "Backup file should be created"
        assert "corrupt" in backup.read_text(), "Backup should contain original content"

    def test_repair_ledger_no_backup_when_clean(self, tmp_path: Path):
        """Test that no backup is created when file is already valid."""
        ledger = tmp_path / "test_ledger.jsonl"
        
        ledger.write_text(
            '{"valid": true}\n'
            '{"also_valid": true}\n'
        )
        
        valid, discarded = repair_ledger(ledger)
        
        assert valid == 2
        assert discarded == 0
        assert not (tmp_path / "test_ledger.jsonl.bak").exists()

    def test_repair_ledger_handles_empty_file(self, tmp_path: Path):
        """Test repair_ledger with empty file."""
        ledger = tmp_path / "empty.jsonl"
        ledger.write_text("")
        
        valid, discarded = repair_ledger(ledger)
        
        assert valid == 0
        assert discarded == 0

    def test_repair_ledger_handles_missing_file(self, tmp_path: Path):
        """Test repair_ledger with non-existent file."""
        ledger = tmp_path / "nonexistent.jsonl"
        
        valid, discarded = repair_ledger(ledger)
        
        assert valid == 0
        assert discarded == 0

    def test_repaired_file_contains_only_valid_json(self, tmp_path: Path):
        """Test that repaired file contains only valid JSON lines."""
        ledger = tmp_path / "test_ledger.jsonl"
        
        ledger.write_text(
            '{"id": 1}\n'
            'bad line\n'
            '{"id": 2}\n'
        )
        
        repair_ledger(ledger)
        
        # Read repaired file and verify all lines are valid JSON
        for line in ledger.read_text().strip().split("\n"):
            entry = json.loads(line)  # Should not raise
            assert "id" in entry
