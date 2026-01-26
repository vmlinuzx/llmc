"""
Tests for file-level descriptions generation.

Tests the file_descriptions module which provides stable file-level
summaries for mcgrep and LLM context.
"""

from pathlib import Path
import sqlite3

from llmc.rag.enrichment.file_descriptions import (
    compute_input_hash,
    generate_all_file_descriptions,
    generate_cheap_description,
    update_file_description,
)


class MockDatabase:
    """Minimal mock of Database for testing."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._setup_schema()

    def _setup_schema(self):
        self.conn.executescript("""
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                lang TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL
            );
            
            CREATE TABLE spans (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES files(id),
                symbol TEXT NOT NULL,
                kind TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                byte_start INTEGER NOT NULL,
                byte_end INTEGER NOT NULL,
                span_hash TEXT NOT NULL UNIQUE,
                doc_hint TEXT
            );
            
            CREATE TABLE enrichments (
                span_hash TEXT PRIMARY KEY,
                summary TEXT,
                tags TEXT
            );
            
            CREATE TABLE file_descriptions (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES files(id),
                file_path TEXT UNIQUE NOT NULL,
                description TEXT,
                source TEXT,
                updated_at DATETIME,
                content_hash TEXT,
                input_hash TEXT
            );
        """)

    def close(self):
        self.conn.close()

    def add_file(self, path: str, file_hash: str = "abc123") -> int:
        self.conn.execute(
            "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
            (path, "python", file_hash, 1000, 12345.0),
        )
        row = self.conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
        return row[0]

    def add_span(
        self, file_id: int, symbol: str, kind: str, span_hash: str, summary: str | None = None
    ):
        self.conn.execute(
            """
            INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, symbol, kind, 1, 10, 0, 100, span_hash),
        )
        if summary:
            self.conn.execute(
                "INSERT INTO enrichments (span_hash, summary) VALUES (?, ?)",
                (span_hash, summary),
            )


class TestComputeInputHash:
    """Tests for input hash computation."""

    def test_stable_hash(self):
        """Hash should be deterministic for same inputs."""
        h1 = compute_input_hash("abc", ["s1", "s2"], "v1")
        h2 = compute_input_hash("abc", ["s1", "s2"], "v1")
        assert h1 == h2

    def test_hash_changes_with_file_hash(self):
        """Hash should change when file content changes."""
        h1 = compute_input_hash("abc", ["s1"], "v1")
        h2 = compute_input_hash("def", ["s1"], "v1")
        assert h1 != h2

    def test_hash_changes_with_span_hashes(self):
        """Hash should change when span content changes."""
        h1 = compute_input_hash("abc", ["s1"], "v1")
        h2 = compute_input_hash("abc", ["s2"], "v1")
        assert h1 != h2

    def test_hash_changes_with_algo_version(self):
        """Hash should change when algorithm version changes."""
        h1 = compute_input_hash("abc", ["s1"], "v1")
        h2 = compute_input_hash("abc", ["s1"], "v2")
        assert h1 != h2

    def test_hash_length(self):
        """Hash should be 16 characters (truncated hex)."""
        h = compute_input_hash("abc", ["s1"], "v1")
        assert len(h) == 16

    def test_hash_only_uses_top_5_spans(self):
        """Hash should only consider first 5 span hashes."""
        h1 = compute_input_hash("abc", ["s1", "s2", "s3", "s4", "s5"], "v1")
        h2 = compute_input_hash("abc", ["s1", "s2", "s3", "s4", "s5", "s6"], "v1")
        assert h1 == h2  # 6th span is ignored


class TestGenerateCheapDescription:
    """Tests for cheap description generation."""

    def test_generates_description_from_spans(self):
        """Should combine span summaries into file description."""
        db = MockDatabase()
        file_id = db.add_file("test.py")
        db.add_span(file_id, "TestClass", "class", "hash1", "Handles user authentication")
        db.add_span(file_id, "login", "function", "hash2", "Validates credentials")

        desc, span_hashes = generate_cheap_description(db, "test.py")
        
        assert desc is not None
        assert "authentication" in desc.lower() or "credentials" in desc.lower()
        assert len(span_hashes) == 2
        db.close()

    def test_returns_none_for_no_enrichments(self):
        """Should return None if no enrichments exist."""
        db = MockDatabase()
        file_id = db.add_file("test.py")
        db.add_span(file_id, "TestClass", "class", "hash1", None)  # No summary

        desc, span_hashes = generate_cheap_description(db, "test.py")
        
        assert desc is None
        assert span_hashes == []
        db.close()

    def test_prioritizes_classes_over_functions(self):
        """Should prioritize class descriptions over functions."""
        db = MockDatabase()
        file_id = db.add_file("test.py")
        # Add function first (should be lower priority)
        db.add_span(file_id, "helper", "function", "hash1", "Helper function")
        # Add class second (should be higher priority)
        db.add_span(file_id, "Router", "class", "hash2", "Main router class")

        desc, span_hashes = generate_cheap_description(db, "test.py")
        
        # Class should appear first in the description
        assert desc is not None
        assert "Router" in desc or "router" in desc.lower()
        db.close()

    def test_limits_word_count(self):
        """Should respect max_words limit."""
        db = MockDatabase()
        file_id = db.add_file("test.py")
        long_summary = " ".join(["word"] * 100)
        db.add_span(file_id, "Test", "class", "hash1", long_summary)

        desc, _ = generate_cheap_description(db, "test.py", max_words=20)
        
        assert desc is not None
        words = desc.replace("...", "").split()
        assert len(words) <= 22  # Allow some overflow for truncation


class TestUpdateFileDescription:
    """Tests for the update_file_description function."""

    def test_creates_new_description(self):
        """Should create description for file without one."""
        db = MockDatabase()
        file_id = db.add_file("test.py", file_hash="content_hash_1")
        db.add_span(file_id, "Test", "class", "hash1", "Test class for testing")

        result = update_file_description(db, "test.py", "content_hash_1")
        
        assert result is True
        
        row = db.conn.execute(
            "SELECT description, source, input_hash FROM file_descriptions WHERE file_path = ?",
            ("test.py",),
        ).fetchone()
        assert row is not None
        assert row["description"] is not None
        assert row["source"] == "cheap"
        assert row["input_hash"] is not None
        db.close()

    def test_skips_if_fresh(self):
        """Should skip update if description is already fresh."""
        db = MockDatabase()
        file_id = db.add_file("test.py", file_hash="content_hash_1")
        db.add_span(file_id, "Test", "class", "hash1", "Test class")
        
        # First update
        update_file_description(db, "test.py", "content_hash_1")
        
        # Get the input_hash that was set
        row = db.conn.execute(
            "SELECT input_hash FROM file_descriptions WHERE file_path = ?",
            ("test.py",),
        ).fetchone()
        original_hash = row["input_hash"]
        
        # Second update should be skipped
        result = update_file_description(db, "test.py", "content_hash_1")
        
        assert result is False
        db.close()

    def test_force_regenerates(self):
        """Should regenerate when force=True."""
        db = MockDatabase()
        file_id = db.add_file("test.py", file_hash="content_hash_1")
        db.add_span(file_id, "Test", "class", "hash1", "Original summary")
        
        # First update
        update_file_description(db, "test.py", "content_hash_1")
        
        # Update the summary
        db.conn.execute("UPDATE enrichments SET summary = 'New summary' WHERE span_hash = 'hash1'")
        
        # Force regenerate
        result = update_file_description(db, "test.py", "content_hash_1", force=True)
        
        assert result is True
        db.close()


class TestGenerateAllFileDescriptions:
    """Tests for batch file description generation."""

    def test_processes_all_enriched_files(self):
        """Should process all files that have enrichments."""
        db = MockDatabase()
        
        # File 1 with enrichment
        file_id1 = db.add_file("file1.py", file_hash="hash1")
        db.add_span(file_id1, "Class1", "class", "span1", "First file description")
        
        # File 2 with enrichment
        file_id2 = db.add_file("file2.py", file_hash="hash2")
        db.add_span(file_id2, "Class2", "class", "span2", "Second file description")
        
        # File 3 without enrichment (should be skipped)
        db.add_file("file3.py", file_hash="hash3")
        
        results = generate_all_file_descriptions(
            db=db,
            repo_root=Path("/tmp"),
            mode="cheap",
        )
        
        assert results["updated"] == 2
        assert results["total"] == 2  # Only enriched files
        db.close()

    def test_calls_progress_callback(self):
        """Should call progress callback during processing."""
        db = MockDatabase()
        file_id = db.add_file("test.py", file_hash="hash1")
        db.add_span(file_id, "Test", "class", "span1", "Summary")
        
        progress_calls = []
        
        def callback(current: int, total: int):
            progress_calls.append((current, total))
        
        generate_all_file_descriptions(
            db=db,
            repo_root=Path("/tmp"),
            mode="cheap",
            progress_callback=callback,
        )
        
        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)
        db.close()
