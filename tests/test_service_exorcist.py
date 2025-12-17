"""
Tests for the nuclear RAG database exorcist.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from llmc.rag.service_exorcist import Exorcist, ExorcistStats


def _build_fake_rag_repo(tmp_path: Path) -> Path:
    """Create a temporary repo with a populated .rag directory."""
    repo = tmp_path / "repo"
    rag_dir = repo / ".rag"
    quality_dir = rag_dir / "quality_reports"

    quality_dir.mkdir(parents=True, exist_ok=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)

    # Index database with spans table and a couple of rows.
    index_db = rag_dir / "rag_index.db"
    conn = sqlite3.connect(index_db)
    try:
        conn.execute("CREATE TABLE spans (id INTEGER PRIMARY KEY, data TEXT)")
        conn.executemany(
            "INSERT INTO spans (data) VALUES (?)",
            [("a",), ("b",)],
        )
        conn.commit()
    finally:
        conn.close()

    # Enrichments JSON with a couple of entries.
    enrichments = rag_dir / "enrichments.json"
    enrichments.write_text(json.dumps([{"span_hash": "x"}, {"span_hash": "y"}]), encoding="utf-8")

    # Embeddings database with embeddings table and rows.
    embeddings_db = rag_dir / "embeddings.db"
    conn = sqlite3.connect(embeddings_db)
    try:
        conn.execute("CREATE TABLE embeddings (id INTEGER PRIMARY KEY, vec BLOB)")
        conn.executemany(
            "INSERT INTO embeddings (vec) VALUES (?)",
            [(b"\x00\x01",), (b"\x02\x03",)],
        )
        conn.commit()
    finally:
        conn.close()

    # Quality reports and failures DB (only size matters here).
    (quality_dir / "report1.json").write_text("{}", encoding="utf-8")
    (quality_dir / "report2.json").write_text("{}", encoding="utf-8")

    failures_db = rag_dir / "failures.db"
    failures_db.write_bytes(b"\x00" * 16)

    return repo


def test_gather_on_empty_repo(tmp_path: Path) -> None:
    """ExorcistStats.gather reports non-existent .rag cleanly."""
    repo = tmp_path / "empty_repo"
    repo.mkdir(parents=True, exist_ok=True)

    stats = ExorcistStats(repo).gather()
    assert stats["exists"] is False
    assert stats["files"] == []
    assert stats["total_size_bytes"] == 0
    assert stats["span_count"] == 0
    assert stats["enrichment_count"] == 0
    assert stats["embedding_count"] == 0


def test_gather_reports_expected_counts(tmp_path: Path) -> None:
    """ExorcistStats.gather returns span/enrichment/embedding counts and files."""
    repo = _build_fake_rag_repo(tmp_path)
    stats = ExorcistStats(repo).gather()

    assert stats["exists"] is True
    # We inserted two rows into each table/collection in the builder.
    assert stats["span_count"] == 2
    assert stats["enrichment_count"] == 2
    assert stats["embedding_count"] == 2

    # There should be at least the main artefacts plus quality reports.
    file_paths = {f["path"] for f in stats["files"]}
    assert ".rag/rag_index.db" in file_paths
    assert ".rag/enrichments.json" in file_paths
    assert ".rag/embeddings.db" in file_paths
    assert any(p.startswith(".rag/quality_reports/") for p in file_paths)
    assert ".rag/failures.db" in file_paths

    # Total size should be positive and match sum of component sizes.
    summed = sum(f["size_bytes"] for f in stats["files"])
    assert summed == stats["total_size_bytes"] > 0


def test_nuke_dry_run_does_not_delete_files(tmp_path: Path) -> None:
    """Dry-run exorcist prints plan but leaves files intact."""
    repo = _build_fake_rag_repo(tmp_path)
    exorcist = Exorcist(repo)

    # Capture initial state.
    stats_before = ExorcistStats(repo).gather()
    assert stats_before["files"]

    # Dry-run should succeed and keep files.
    result = exorcist.nuke(dry_run=True)
    assert result is True

    stats_after = ExorcistStats(repo).gather()
    assert stats_after["files"]
    assert stats_after["total_size_bytes"] == stats_before["total_size_bytes"]


def test_nuke_deletes_rag_artifacts(tmp_path: Path) -> None:
    """Full nuke removes known RAG artefacts but leaves repo directory."""
    repo = _build_fake_rag_repo(tmp_path)
    rag_dir = repo / ".rag"
    exorcist = Exorcist(repo)

    assert rag_dir.exists()

    result = exorcist.nuke(dry_run=False)
    assert result is True

    # The .rag directory should remain, but core artefacts should be gone.
    assert rag_dir.exists()
    assert not (rag_dir / "rag_index.db").exists()
    assert not (rag_dir / "enrichments.json").exists()
    assert not (rag_dir / "embeddings.db").exists()
    assert not (rag_dir / "quality_reports").exists()
    assert not (rag_dir / "failures.db").exists()
