"""
File Description Generator

This module provides functions for generating file-level descriptions from span enrichments.

Two tiers:
- Cheap: Compress top-K span summaries (no LLM call)
- Rich: Use LLM to synthesize file purpose (optional, one call per file)

Staleness tracking via input_hash prevents unnecessary recomputation.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from llmc.rag.config_models import get_default_enrichment_model
from llmc.rag.database import Database

# Algorithm version - bump this to force regeneration of all descriptions
ALGO_VERSION = "v1.1"

def _extract_first_sentence(text: str) -> str:
    """Extract first sentence, handling file extensions like .py, .toml, .git.
    
    Uses '. [A-Z]' pattern to find sentence boundaries, avoiding splits
    on file extensions which are followed by lowercase or space.
    """
    if not text:
        return ""
    
    # Pattern: ". " followed by capital letter indicates new sentence
    match = re.search(r'\.\s+[A-Z]', text)
    if match:
        return text[:match.start() + 1].strip()
    
    # No sentence break found, return whole text
    return text.strip()



def compute_input_hash(file_hash: str, span_hashes: list[str], algo_version: str = ALGO_VERSION) -> str:
    """Compute hash for staleness detection.
    
    If the hash changes, the description needs regeneration.
    
    Args:
        file_hash: Hash of the file content
        span_hashes: Hashes of top spans (order matters)
        algo_version: Algorithm version string
        
    Returns:
        16-char hex hash
    """
    data = file_hash + "".join(span_hashes[:5]) + algo_version
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _get_important_spans(db: Database, file_path: str, limit: int = 5) -> list[dict[str, Any]]:
    """Get the most important spans for a file, prioritized by type.
    
    Priority order:
    1. Module-level docstrings (kind='module')
    2. Class definitions (kind='class')
    3. Top-level functions (kind='function' with no '.' in symbol)
    4. Other spans by start_line
    """
    rows = db.conn.execute(
        """
        SELECT 
            s.span_hash,
            s.symbol,
            s.kind,
            s.start_line,
            e.summary
        FROM spans s
        JOIN files f ON s.file_id = f.id
        LEFT JOIN enrichments e ON s.span_hash = e.span_hash
        WHERE f.path = ? AND e.summary IS NOT NULL
        ORDER BY 
            CASE 
                WHEN s.kind = 'module' THEN 1
                WHEN s.kind = 'class' THEN 2
                WHEN s.kind = 'function' AND s.symbol NOT LIKE '%.%' THEN 3
                ELSE 4
            END,
            s.start_line
        LIMIT ?
        """,
        (file_path, limit),
    ).fetchall()
    
    return [
        {
            "span_hash": row[0],
            "symbol": row[1],
            "kind": row[2],
            "start_line": row[3],
            "summary": row[4],
        }
        for row in rows
    ]


def generate_cheap_description(db: Database, file_path: str, max_words: int = 50) -> tuple[str | None, list[str]]:
    """
    Generate a file description by intelligently compressing span summaries.
    
    Prioritizes important spans (module docstrings, classes, top-level functions)
    and limits output to ~50 words.
    
    Args:
        db: Database connection
        file_path: Path to the file
        max_words: Maximum words in description
        
    Returns:
        Tuple of (description, span_hashes) where span_hashes are the hashes
        of spans used to generate the description (for staleness tracking)
    """
    spans = _get_important_spans(db, file_path, limit=5)
    
    if not spans:
        return None, []
    
    # Collect summaries, preferring first sentence for brevity
    summaries = []
    span_hashes = []
    word_count = 0
    
    for span in spans:
        summary = span["summary"]
        if not summary:
            continue
            
        # Take first sentence only
        first_sentence = _extract_first_sentence(summary)
        if not first_sentence:
            continue
            
        sentence_words = len(first_sentence.split())
        
        # Stop if adding this would exceed limit
        if word_count + sentence_words > max_words:
            if summaries:  # Only break if we have at least one
                break
            # If first summary is too long, truncate it
            words = first_sentence.split()[:max_words]
            first_sentence = " ".join(words) + "..."
            
        summaries.append(first_sentence)
        span_hashes.append(span["span_hash"])
        word_count += sentence_words
    
    if not summaries:
        return None, []
    
    # Join with periods
    description = ". ".join(s.rstrip(".") for s in summaries)
    if not description.endswith("."):
        description += "."
        
    return description, span_hashes


def generate_rich_description(
    db: Database, 
    file_path: str, 
    repo_root: Path,
    model: str | None = None
) -> tuple[str | None, list[str]]:
    """
    Generate a file description using an LLM to summarize the file's purpose.
    
    This is the "rich" tier that makes one LLM call per file.
    
    Args:
        db: Database connection
        file_path: Path to the file
        repo_root: Repository root for reading file content
        model: Ollama model to use
        
    Returns:
        Tuple of (description, span_hashes) for staleness tracking
    """
    try:
        import httpx
    except ImportError:
        return None, []
    
    # Get spans for context
    spans = _get_important_spans(db, file_path, limit=5)
    span_hashes = [s["span_hash"] for s in spans]
    
    # Read file content
    full_path = repo_root / file_path
    if not full_path.exists():
        return None, span_hashes
        
    try:
        content = full_path.read_text(errors="ignore")[:3000]  # First 3000 chars
    except Exception:
        return None, span_hashes
    
    # Build prompt
    resolved_model = model or get_default_enrichment_model(repo_root)
    span_symbols = [s["symbol"] for s in spans[:5]]
    prompt = f"""Summarize the purpose of this file in ~50 words.
Focus on: what it does, key exports, and how it fits the codebase.
Be terse. No filler words.

File: {file_path}
Key symbols: {', '.join(span_symbols)}

Content (first 3000 chars):
{content}

Summary (one paragraph, ~50 words):"""

    # Call Ollama
    try:
        response = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": resolved_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        description = result.get("response", "").strip()
        
        # Clean up - take first paragraph only
        description = description.split("\n\n")[0].strip()
        
        # Limit to ~60 words
        words = description.split()
        if len(words) > 60:
            description = " ".join(words[:60]) + "..."
            
        return description, span_hashes
        
    except Exception:
        return None, span_hashes


def update_file_description(
    db: Database, 
    file_path: str, 
    content_hash: str,
    mode: str = "cheap",
    repo_root: Path | None = None,
    force: bool = False,
) -> bool:
    """
    Update the file description in the database if needed.
    
    Uses staleness detection via input_hash to avoid unnecessary regeneration.
    
    Args:
        db: Database connection
        file_path: Path to the file
        content_hash: Hash of file content (from files table)
        mode: "cheap" (span compression) or "rich" (LLM)
        repo_root: Required for rich mode
        force: Force regeneration even if not stale
        
    Returns:
        True if description was updated, False if skipped (already fresh)
    """
    # Get file_id
    file_id_row = db.conn.execute(
        "SELECT id FROM files WHERE path = ?", (file_path,)
    ).fetchone()
    if not file_id_row:
        return False
    file_id = file_id_row[0]
    
    # Check staleness
    if not force:
        existing = db.conn.execute(
            "SELECT input_hash FROM file_descriptions WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        
        if existing and existing[0]:
            # Get current span hashes to compute expected input_hash
            spans = _get_important_spans(db, file_path, limit=5)
            span_hashes = [s["span_hash"] for s in spans]
            expected_hash = compute_input_hash(content_hash, span_hashes)
            
            if existing[0] == expected_hash:
                return False  # Already fresh
    
    # Generate description based on mode
    if mode == "rich" and repo_root:
        description, span_hashes = generate_rich_description(
            db, file_path, repo_root
        )
        source = "rich"
    else:
        description, span_hashes = generate_cheap_description(db, file_path)
        source = "cheap"
    
    if not description:
        return False
    
    # Compute input hash for staleness tracking
    input_hash = compute_input_hash(content_hash, span_hashes)
    
    # Upsert
    db.conn.execute(
        """
        INSERT INTO file_descriptions 
            (file_id, file_path, description, source, updated_at, content_hash, input_hash)
        VALUES (?, ?, ?, ?, strftime('%s','now'), ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            description = excluded.description,
            source = excluded.source,
            updated_at = excluded.updated_at,
            content_hash = excluded.content_hash,
            input_hash = excluded.input_hash
        """,
        (file_id, file_path, description, source, content_hash, input_hash),
    )
    db.conn.commit()
    return True


def generate_all_file_descriptions(
    db: Database,
    repo_root: Path,
    mode: str = "cheap",
    force: bool = False,
    progress_callback: callable | None = None,
) -> dict[str, int]:
    """
    Generate descriptions for all files in the database.
    
    Args:
        db: Database connection
        repo_root: Repository root
        mode: "cheap" or "rich"
        force: Force regeneration even if fresh
        progress_callback: Optional callback(current, total) for progress
        
    Returns:
        Dict with counts: {"updated": N, "skipped": M, "failed": F}
    """
    # Get all files with content hashes
    rows = db.conn.execute(
        """
        SELECT f.path, f.file_hash
        FROM files f
        WHERE EXISTS (
            SELECT 1 FROM spans s 
            JOIN enrichments e ON s.span_hash = e.span_hash
            WHERE s.file_id = f.id
        )
        """
    ).fetchall()
    
    total = len(rows)
    updated = 0
    skipped = 0
    failed = 0
    
    for i, row in enumerate(rows):
        file_path = row[0]
        file_hash = row[1]
        
        if progress_callback:
            progress_callback(i + 1, total)
        
        try:
            if update_file_description(
                db, file_path, file_hash, mode=mode, repo_root=repo_root, force=force
            ):
                updated += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
    
    return {"updated": updated, "skipped": skipped, "failed": failed, "total": total}
