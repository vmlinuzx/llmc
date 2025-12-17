"""
Tech Docs Graph Edge Writer

Writes graph edges from tech docs enrichment to the database.
Implements Phase 4 of Domain RAG Tech Docs (SDD Section 6).

Edge types:
- REFERENCES: From `related_topics` field (cross-references)
- REQUIRES: From `prerequisites` field (depends on)
- WARNS_ABOUT: From `warnings` field (caution about)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from llmc.rag.graph import EdgeType, GraphEdge

if TYPE_CHECKING:
    from llmc.rag.database import Database
    from llmc.rag.schemas.tech_docs_enrichment import TechDocsEnrichment

logger = logging.getLogger(__name__)


# SQL to create edges table in main RAG database
# Note: UNIQUE on target_text (not target_span_hash) to handle NULL targets
# SQLite treats each NULL as unique, so we use target_text for deduplication
EDGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tech_docs_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_span_hash TEXT NOT NULL,
    target_span_hash TEXT,
    edge_type TEXT NOT NULL,
    target_text TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    pattern_id TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_span_hash, edge_type, target_text),
    FOREIGN KEY (source_span_hash) REFERENCES spans(span_hash) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tech_docs_edges_source ON tech_docs_edges(source_span_hash);
CREATE INDEX IF NOT EXISTS idx_tech_docs_edges_target ON tech_docs_edges(target_span_hash);
CREATE INDEX IF NOT EXISTS idx_tech_docs_edges_type ON tech_docs_edges(edge_type);
"""


@dataclass
class EdgeWriteResult:
    """Result of writing tech docs edges."""
    edges_created: int
    edges_skipped: int  # Duplicates
    edges_unresolved: int  # No target found
    errors: list[str]


def ensure_edges_table(db: "Database") -> bool:
    """Ensure the tech_docs_edges table exists.
    
    Returns True if table was created/exists, False on error.
    """
    try:
        cursor = db.conn.cursor()
        cursor.executescript(EDGES_TABLE_SQL)
        db.conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to create tech_docs_edges table: {e}")
        return False


def find_span_by_topic(
    db: "Database",
    topic: str,
    source_file_path: str | None = None,
) -> str | None:
    """Find a span matching the given topic name.
    
    Resolution strategy:
    1. Exact symbol match (case-insensitive)
    2. Symbol contains topic (for qualified names like "module.ClassName")
    3. FTS search if available
    4. File path match (for "See INSTALLATION.md" references)
    
    Args:
        db: Database instance
        topic: Topic name to search for (e.g., "OAuth 2.0", "TechDocsExtractor")
        source_file_path: Path of source doc (for relative link resolution)
        
    Returns:
        span_hash if found, None otherwise
    """
    cursor = db.conn.cursor()
    
    # Normalize topic for matching
    topic_normalized = topic.strip().lower()
    if not topic_normalized:
        return None
    
    # Strategy 1: Exact symbol match
    cursor.execute("""
        SELECT span_hash FROM spans 
        WHERE LOWER(symbol) = ?
        LIMIT 1
    """, (topic_normalized,))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Strategy 2: Symbol contains topic (partial match for qualified names)
    cursor.execute("""
        SELECT span_hash FROM spans 
        WHERE LOWER(symbol) LIKE ?
        ORDER BY LENGTH(symbol)
        LIMIT 1
    """, (f"%{topic_normalized}%",))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Strategy 3: File path match (for doc cross-references)
    # Handle "See README.md" or "Installation Guide" -> "INSTALLATION.md"
    possible_paths = [
        topic,  # Exact filename
        topic.replace(" ", "_") + ".md",  # "Installation Guide" -> "Installation_Guide.md"
        topic.replace(" ", "-") + ".md",  # "Installation Guide" -> "Installation-Guide.md"
    ]
    for path_pattern in possible_paths:
        cursor.execute("""
            SELECT s.span_hash 
            FROM spans s
            JOIN files f ON s.file_id = f.id
            WHERE LOWER(f.path) LIKE ?
            LIMIT 1
        """, (f"%{path_pattern.lower()}%",))
        result = cursor.fetchone()
        if result:
            return result[0]
    
    # Strategy 4: FTS search (if available)
    if db.fts_available:
        try:
            # Use the enrichment summary search to find related spans
            cursor.execute("""
                SELECT e.span_hash
                FROM enrichments e
                JOIN enrichments_fts fts ON e.rowid = fts.rowid
                WHERE enrichments_fts MATCH ?
                LIMIT 1
            """, (topic_normalized,))
            result = cursor.fetchone()
            if result:
                return result[0]
        except sqlite3.Error:
            pass  # FTS might not be available or topic might not be valid
    
    return None


def write_tech_docs_edges(
    db: "Database",
    span_hash: str,
    enrichment: "TechDocsEnrichment",
    *,
    source_file_path: str | None = None,
    confidence_base: float = 0.8,
) -> EdgeWriteResult:
    """Write graph edges from tech docs enrichment.
    
    Creates edges based on enrichment fields:
    - related_topics -> REFERENCES edges
    - prerequisites -> REQUIRES edges  
    - warnings -> WARNS_ABOUT edges (stored but may not have targets)
    
    Edge creation is idempotent - duplicates are skipped.
    
    Args:
        db: Database instance
        span_hash: Source span's hash
        enrichment: Parsed TechDocsEnrichment object
        source_file_path: Optional path for relative link resolution
        confidence_base: Base confidence score for edges
        
    Returns:
        EdgeWriteResult with counts and any errors
    """
    # Ensure edges table exists
    if not ensure_edges_table(db):
        return EdgeWriteResult(
            edges_created=0,
            edges_skipped=0,
            edges_unresolved=0,
            errors=["Failed to create edges table"]
        )
    
    edges_created = 0
    edges_skipped = 0
    edges_unresolved = 0
    errors: list[str] = []
    
    cursor = db.conn.cursor()
    
    def add_edge(target_text: str, edge_type: EdgeType, pattern_id: str) -> None:
        nonlocal edges_created, edges_skipped, edges_unresolved
        
        # Try to resolve target to a span
        target_hash = find_span_by_topic(db, target_text, source_file_path)
        
        try:
            # Insert edge (UNIQUE constraint handles duplicates)
            cursor.execute("""
                INSERT OR IGNORE INTO tech_docs_edges 
                (source_span_hash, target_span_hash, edge_type, target_text, confidence, pattern_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                span_hash,
                target_hash,  # May be None if unresolved
                edge_type.value,
                target_text,
                confidence_base if target_hash else confidence_base * 0.5,  # Lower confidence for unresolved
                pattern_id,
                json.dumps({"resolved": target_hash is not None})
            ))
            
            if cursor.rowcount > 0:
                edges_created += 1
                logger.debug(
                    f"Created {edge_type.value} edge: {span_hash[:8]} -> "
                    f"{target_hash[:8] if target_hash else 'unresolved'} ({target_text})"
                )
            else:
                edges_skipped += 1
                
            if target_hash is None:
                edges_unresolved += 1
                
        except sqlite3.Error as e:
            errors.append(f"Failed to create {edge_type.value} edge for '{target_text}': {e}")
    
    # Process related_topics -> REFERENCES
    for topic in enrichment.related_topics:
        add_edge(topic, EdgeType.REFERENCES, "related_topics")
    
    # Process prerequisites -> REQUIRES
    for prereq in enrichment.prerequisites:
        add_edge(prereq, EdgeType.REQUIRES, "prerequisites")
    
    # Process warnings -> WARNS_ABOUT
    # Warnings are often free text without targets, but we store them anyway
    for warning in enrichment.warnings:
        add_edge(warning, EdgeType.WARNS_ABOUT, "warnings")
    
    db.conn.commit()
    
    return EdgeWriteResult(
        edges_created=edges_created,
        edges_skipped=edges_skipped,
        edges_unresolved=edges_unresolved,
        errors=errors
    )


def get_tech_docs_edges_stats(db: "Database") -> dict:
    """Get statistics about tech docs edges.
    
    Returns:
        Dict with edge counts by type and resolution status.
    """
    try:
        cursor = db.conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tech_docs_edges'
        """)
        if not cursor.fetchone():
            return {"total": 0, "by_type": {}, "resolved": 0, "unresolved": 0}
        
        # Total edges
        cursor.execute("SELECT COUNT(*) FROM tech_docs_edges")
        total = cursor.fetchone()[0]
        
        # By type
        cursor.execute("""
            SELECT edge_type, COUNT(*) 
            FROM tech_docs_edges 
            GROUP BY edge_type
        """)
        by_type = dict(cursor.fetchall())
        
        # Resolved vs unresolved
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN target_span_hash IS NOT NULL THEN 1 ELSE 0 END) as resolved,
                SUM(CASE WHEN target_span_hash IS NULL THEN 1 ELSE 0 END) as unresolved
            FROM tech_docs_edges
        """)
        row = cursor.fetchone()
        resolved = row[0] or 0
        unresolved = row[1] or 0
        
        return {
            "total": total,
            "by_type": by_type,
            "resolved": resolved,
            "unresolved": unresolved
        }
        
    except sqlite3.Error as e:
        logger.error(f"Failed to get edge stats: {e}")
        return {"total": 0, "by_type": {}, "resolved": 0, "unresolved": 0, "error": str(e)}
