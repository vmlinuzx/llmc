"""Data Export & Dump Utility

Simple data export functionality for backing up LLMC data.

Usage:
    python -m tools.rag.export_data
    # Or via CLI: llmc export
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import struct
import tarfile
import time

import numpy as np


def export_all_data(repo_root: Path, output_path: Path | None = None) -> Path:
    """Export all LLMC data to a timestamped tar.gz archive.

    Exports:
    - chunks.jsonl: All code chunks with metadata
    - embeddings.npy: Embedding vectors (if available)
    - metadata.json: Configuration snapshot and stats

    Args:
        repo_root: Repository root path
        output_path: Custom output path (default: llmc-export-{timestamp}.tar.gz)

    Returns:
        Path to created archive
    """
    # Generate output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = repo_root / f"llmc-export-{timestamp}.tar.gz"

    db_path = repo_root / ".rag" / "index.db"

    if not db_path.exists():
        raise FileNotFoundError(f"No RAG database found at {db_path}")

    # Create temporary directory for export files
    temp_dir = repo_root / ".rag" / "export_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Export chunks to JSONL
        chunks_file = temp_dir / "chunks.jsonl"
        _export_chunks(db_path, chunks_file)

        # Export embeddings to NPY
        embeddings_file = temp_dir / "embeddings.npy"
        embedding_count = _export_embeddings(db_path, embeddings_file)

        # Export metadata
        metadata_file = temp_dir / "metadata.json"
        _export_metadata(db_path, repo_root, metadata_file, embedding_count)

        # Create tar.gz archive
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(chunks_file, arcname="chunks.jsonl")
            if embedding_count > 0:
                tar.add(embeddings_file, arcname="embeddings.npy")
            tar.add(metadata_file, arcname="metadata.json")

        return output_path
    finally:
        # Cleanup temp files
        if chunks_file.exists():
            chunks_file.unlink()
        if embeddings_file.exists():
            embeddings_file.unlink()
        if metadata_file.exists():
            metadata_file.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()


def _export_chunks(db_path: Path, output_file: Path) -> int:
    """Export all chunks to JSONL format."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT 
            files.path,
            files.lang,
            spans.symbol,
            spans.kind,
            spans.start_line,
            spans.end_line,
            spans.span_hash,
            spans.doc_hint
        FROM spans
        JOIN files ON spans.file_id = files.id
        ORDER BY files.path, spans.start_line
    """
    )

    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for row in cursor:
            chunk = {
                "file_path": row["path"],
                "language": row["lang"],
                "symbol": row["symbol"],
                "kind": row["kind"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "span_hash": row["span_hash"],
                "doc_hint": row["doc_hint"],
            }
            f.write(json.dumps(chunk) + "\n")
            count += 1

    conn.close()
    return count


def _export_embeddings(db_path: Path, output_file: Path) -> int:
    """Export embeddings to NumPy format."""
    conn = sqlite3.connect(str(db_path))

    cursor = conn.execute("SELECT vec FROM embeddings ORDER BY span_hash")

    vectors = []
    for row in cursor:
        blob = row[0]
        dim = len(blob) // 4
        vector = list(struct.unpack(f"<{dim}f", blob))
        vectors.append(vector)

    conn.close()

    if vectors:
        embeddings_array = np.array(vectors, dtype=np.float32)
        np.save(output_file, embeddings_array)
        return len(vectors)

    return 0


def _export_metadata(
    db_path: Path, repo_root: Path, output_file: Path, embedding_count: int
) -> None:
    """Export metadata and stats."""
    conn = sqlite3.connect(str(db_path))

    # Get stats
    cursor = conn.execute("SELECT COUNT(*) FROM files")
    file_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM spans")
    span_count = cursor.fetchone()[0]

    # Get embedding model info (if available)
    embedding_model = None
    embedding_dim = None
    try:
        cursor = conn.execute("SELECT model, dim FROM embeddings_meta LIMIT 1")
        row = cursor.fetchone()
        if row:
            embedding_model = row[0]
            embedding_dim = row[1]
    except Exception:
        pass

    conn.close()

    metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "repo_root": str(repo_root),
        "stats": {
            "files": file_count,
            "spans": span_count,
            "embeddings": embedding_count,
        },
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dim,
        "llmc_version": "2.2.0",
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def run_export(repo_root: Path | None = None, output_path: Path | None = None) -> None:
    """Run export and print results."""
    from .utils import find_repo_root

    repo = repo_root or find_repo_root()

    print(f"Exporting LLMC data from {repo}...")
    start_time = time.time()

    try:
        archive_path = export_all_data(repo, output_path)
        duration = time.time() - start_time

        # Get archive size
        size_mb = archive_path.stat().st_size / (1024 * 1024)

        print("\n✅ Export complete!")
        print(f"   Archive: {archive_path}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Duration: {duration:.2f}s")
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export LLMC data")
    parser.add_argument("--output", "-o", type=Path, help="Output archive path")
    parser.add_argument("--repo", type=Path, help="Repository root path")

    args = parser.parse_args()

    run_export(repo_root=args.repo, output_path=args.output)
