"""Tests for observability module (M4)."""

from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path

from llmc_mcp.config import McpObservabilityConfig
from llmc_mcp.observability import (
    JsonLogFormatter,
    MetricsCollector,
    ObservabilityContext,
    TokenAuditWriter,
    generate_correlation_id,
    setup_logging,
)


class TestCorrelationId(unittest.TestCase):
    """Test correlation ID generation."""
    
    def test_generates_8_char_id(self):
        cid = generate_correlation_id()
        self.assertEqual(len(cid), 8)
    
    def test_generates_unique_ids(self):
        ids = {generate_correlation_id() for _ in range(100)}
        self.assertEqual(len(ids), 100, "Should generate unique IDs")
    
    def test_is_hex_string(self):
        cid = generate_correlation_id()
        # UUID hex chars only
        self.assertTrue(all(c in "0123456789abcdef-" for c in cid))


class TestJsonLogFormatter(unittest.TestCase):
    """Test JSON log formatting."""
    
    def test_basic_format(self):
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        
        self.assertEqual(data["level"], "info")
        self.assertEqual(data["logger"], "test")
        self.assertEqual(data["msg"], "Hello world")
        self.assertIn("ts", data)
    
    def test_includes_correlation_id(self):
        formatter = JsonLogFormatter(include_correlation_id=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc12345"
        
        output = formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["cid"], "abc12345")
    
    def test_includes_session_id(self):
        os.environ["TE_SESSION_ID"] = "sess_123"
        try:
            formatter = JsonLogFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            
            output = formatter.format(record)
            data = json.loads(output)
            self.assertEqual(data["session_id"], "sess_123")
        finally:
            del os.environ["TE_SESSION_ID"]
    
    def test_includes_extra_fields(self):
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.tool = "read_file"
        record.latency_ms = 42.5
        record.status = "ok"
        
        output = formatter.format(record)
        data = json.loads(output)
        
        self.assertEqual(data["tool"], "read_file")
        self.assertEqual(data["latency_ms"], 42.5)
        self.assertEqual(data["status"], "ok")



class TestMetricsCollector(unittest.TestCase):
    """Test in-memory metrics collection."""
    
    def setUp(self):
        self.collector = MetricsCollector()
    
    def test_records_call(self):
        self.collector.record_call("read_file", latency_ms=10.0, success=True)
        stats = self.collector.get_stats()
        
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["total_errors"], 0)
        self.assertIn("read_file", stats["tools"])
        self.assertEqual(stats["tools"]["read_file"]["calls"], 1)
    
    def test_tracks_errors(self):
        self.collector.record_call("read_file", latency_ms=5.0, success=True)
        self.collector.record_call("read_file", latency_ms=10.0, success=False)
        
        stats = self.collector.get_stats()
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["total_errors"], 1)
        self.assertEqual(stats["tools"]["read_file"]["errors"], 1)
    
    def test_tracks_latency_stats(self):
        self.collector.record_call("stat", latency_ms=5.0, success=True)
        self.collector.record_call("stat", latency_ms=15.0, success=True)
        self.collector.record_call("stat", latency_ms=10.0, success=True)
        
        stats = self.collector.get_stats()
        tool_stats = stats["tools"]["stat"]
        
        self.assertEqual(tool_stats["min_ms"], 5.0)
        self.assertEqual(tool_stats["max_ms"], 15.0)
        self.assertEqual(tool_stats["avg_ms"], 10.0)
    
    def test_tracks_tokens(self):
        self.collector.record_call("rag_search", latency_ms=50.0, success=True, 
                                   tokens_in=100, tokens_out=500)
        
        stats = self.collector.get_stats()
        self.assertEqual(stats["tokens_in"], 100)
        self.assertEqual(stats["tokens_out"], 500)
    
    def test_reset(self):
        self.collector.record_call("test", latency_ms=10.0, success=True)
        self.collector.reset()
        
        stats = self.collector.get_stats()
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(len(stats["tools"]), 0)


class TestTokenAuditWriter(unittest.TestCase):
    """Test CSV audit trail writer."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = Path(self.temp_dir) / "audit.csv"
    
    def tearDown(self):
        if self.csv_path.exists():
            os.unlink(self.csv_path)
        os.rmdir(self.temp_dir)
    
    def test_creates_file_with_headers(self):
        writer = TokenAuditWriter(self.csv_path, enabled=True)
        writer.record("abc123", "read_file", 10, 100, 5.0, True)
        
        self.assertTrue(self.csv_path.exists())
        
        with open(self.csv_path) as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertIn("correlation_id", headers)
            self.assertIn("tool", headers)
            self.assertIn("tokens_in", headers)
    
    def test_appends_records(self):
        writer = TokenAuditWriter(self.csv_path, enabled=True)
        writer.record("abc123", "read_file", 10, 100, 5.0, True)
        writer.record("def456", "list_dir", 5, 50, 3.0, True)
        
        with open(self.csv_path) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 3)  # header + 2 records
    
    def test_disabled_does_not_write(self):
        writer = TokenAuditWriter(self.csv_path, enabled=False)
        writer.record("abc123", "read_file", 10, 100, 5.0, True)
        
        self.assertFalse(self.csv_path.exists())



class TestObservabilityContext(unittest.TestCase):
    """Test unified observability context."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = Path(self.temp_dir) / "audit.csv"
        self.config = McpObservabilityConfig(
            enabled=True,
            csv_token_audit_enabled=True,
            csv_path=str(self.csv_path),
        )
    
    def tearDown(self):
        if self.csv_path.exists():
            os.unlink(self.csv_path)
        os.rmdir(self.temp_dir)
    
    def test_generates_correlation_id(self):
        obs = ObservabilityContext(self.config)
        cid = obs.correlation_id()
        self.assertEqual(len(cid), 8)
    
    def test_records_to_metrics_and_audit(self):
        obs = ObservabilityContext(self.config)
        obs.record("abc123", "read_file", latency_ms=10.0, success=True, 
                   tokens_in=5, tokens_out=50)
        
        # Check metrics
        stats = obs.get_stats()
        self.assertEqual(stats["total_requests"], 1)
        
        # Check CSV
        self.assertTrue(self.csv_path.exists())
    
    def test_disabled_skips_recording(self):
        config = McpObservabilityConfig(enabled=False)
        obs = ObservabilityContext(config)
        obs.record("abc123", "read_file", latency_ms=10.0, success=True)
        
        # Metrics still collected (collector always available)
        stats = obs.get_stats()
        self.assertEqual(stats["total_requests"], 0)


class TestSetupLogging(unittest.TestCase):
    """Test logging setup function."""
    
    def test_json_format(self):
        config = McpObservabilityConfig(
            enabled=True,
            log_format="json",
            log_level="info",
        )
        logger = setup_logging(config, "test-json")
        
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0].formatter, JsonLogFormatter)
    
    def test_text_format(self):
        config = McpObservabilityConfig(
            enabled=True,
            log_format="text",
            log_level="debug",
        )
        logger = setup_logging(config, "test-text")
        
        self.assertEqual(len(logger.handlers), 1)
        self.assertNotIsInstance(logger.handlers[0].formatter, JsonLogFormatter)
        self.assertEqual(logger.level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
