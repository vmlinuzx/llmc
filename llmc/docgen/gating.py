"""
Gating logic for docgen - SHA256 and RAG freshness checks.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to file to hash
        
    Returns:
        Hex string of SHA256 hash
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read in 64kb chunks to handle large files
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def read_doc_sha256(doc_path: Path) -> str | None:
    """Read SHA256 hash from first line of documentation file.
    
    Expected format:
        SHA256: <hash>
        
    Args:
        doc_path: Path to documentation file
        
    Returns:
        SHA256 hash if found and valid, None otherwise
    """
    if not doc_path.exists():
        return None
    
    try:
        with open(doc_path, encoding="utf-8") as f:
            first_line = f.readline().strip()
            
        # Check for "SHA256: <hash>" format
        if not first_line.startswith("SHA256:"):
            logger.debug(f"Doc {doc_path} missing SHA256 header")
            return None
        
        # Extract hash (everything after "SHA256: ")
        sha_part = first_line[7:].strip()
        
        # Validate it's a 64-character hex string
        if len(sha_part) != 64:
            logger.warning(
                f"Doc {doc_path} has malformed SHA256 header "
                f"(expected 64 chars, got {len(sha_part)})"
            )
            return None
        
        # Validate hex characters
        try:
            int(sha_part, 16)
        except ValueError:
            logger.warning(
                f"Doc {doc_path} has malformed SHA256 header "
                f"(contains non-hex characters)"
            )
            return None
        
        return sha_part
        
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read doc {doc_path}: {e}")
        return None


def should_skip_sha_gate(
    source_path: Path,
    doc_path: Path,
) -> tuple[bool, str]:
    """Check if doc should be skipped based on SHA256 comparison.
    
    Args:
        source_path: Path to source file
        doc_path: Path to documentation file
        
    Returns:
        Tuple of (should_skip, reason)
        - should_skip: True if doc exists and SHA matches
        - reason: Human-readable reason for decision
    """
    # If doc doesn't exist, don't skip (need to generate)
    if not doc_path.exists():
        return (False, "Doc does not exist")
    
    # Compute source file SHA
    try:
        source_sha = compute_file_sha256(source_path)
    except Exception as e:
        # Can't compute source SHA, don't skip (will fail later if critical)
        logger.warning(f"Failed to compute SHA for {source_path}: {e}")
        return (False, f"Failed to compute source SHA: {e}")
    
    # Read doc SHA
    doc_sha = read_doc_sha256(doc_path)
    
    if doc_sha is None:
        # Doc exists but has no/invalid SHA header, regenerate
        return (False, "Doc exists but missing valid SHA256 header")
    
    # Compare SHAs
    if source_sha == doc_sha:
        # SHA matches, skip regeneration
        return (True, f"SHA256 match ({source_sha[:8]}...)")
    else:
        # SHA differs, regenerate
        return (
            False,
            f"SHA256 mismatch (source: {source_sha[:8]}..., "
            f"doc: {doc_sha[:8]}...)"
        )


def resolve_doc_path(
    repo_root: Path,
    relative_path: Path,
    output_dir: str = "DOCS/REPODOCS",
) -> Path:
    """Resolve documentation output path for a source file.
    
    Args:
        repo_root: Absolute path to repository root
        relative_path: Path relative to repo root (e.g., "tools/rag/database.py")
        output_dir: Output directory relative to repo root
        
    Returns:
        Absolute path to documentation file (e.g., "repo/DOCS/REPODOCS/tools/rag/database.py.md")
    """
    # Construct: repo_root / output_dir / relative_path.md
    doc_path = repo_root / output_dir / f"{relative_path}.md"
    return doc_path


def check_rag_freshness(
    db: Any,  # Database type from tools.rag.database
    relative_path: Path,
    file_sha256: str,
) -> tuple[bool, str]:
    """Check if file is indexed in RAG and up-to-date.
    
    Args:
        db: RAG database instance
        relative_path: Path relative to repo root
        file_sha256: Expected SHA256 hash of file
        
    Returns:
        Tuple of (is_fresh, reason)
        - is_fresh: True if file is indexed and hash matches
        - reason: Human-readable reason for decision
    """
    from tools.rag.database import Database
    
    if not isinstance(db, Database):
        raise TypeError(f"Expected Database instance, got {type(db)}")
    
    # Convert relative path to string for DB query
    path_str = str(relative_path)
    
    # Query for file in RAG database
    try:
        cursor = db.conn.execute(
            "SELECT file_hash FROM files WHERE path = ?",
            (path_str,)
        )
        row = cursor.fetchone()
    except Exception as e:
        logger.error(f"Failed to query RAG DB for {path_str}: {e}")
        return (False, f"RAG DB query failed: {e}")
    
    # File not in RAG
    if row is None:
        return (False, "SKIP_NOT_INDEXED: File not found in RAG database")
    
    # Check hash match
    db_file_hash = row[0]
    
    if db_file_hash != file_sha256:
        return (
            False,
            f"SKIP_STALE_INDEX: RAG hash mismatch "
            f"(expected: {file_sha256[:8]}..., got: {db_file_hash[:8]}...)"
        )
    
    # File is indexed and fresh
    return (True, f"RAG index fresh ({file_sha256[:8]}...)")
