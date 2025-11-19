
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class EnrichmentRecord:
    # Matches structure of 'enrichments' table and relevant 'spans' columns
    span_hash: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    summary: Optional[str] = None
    usage_guide: Optional[str] = None
    # Additional fields can be added here as needed (inputs, outputs, etc.)
    # For now, we focus on the core ones defined in SDD

from tools.rag.config import index_path_for_read

def get_enrichment_db_path(repo_root: Path) -> Path:
    """Returns the path to the enrichment database for a given repo."""
    return index_path_for_read(repo_root)

def load_enrichment_data(repo_root: Path) -> Dict[str, List[EnrichmentRecord]]:
    """
    Loads all enrichment data from the SQLite DB for a repo.
    Returns a dict mapping span_hash to a list of EnrichmentRecords.
    """
    db_path = get_enrichment_db_path(repo_root)
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()

        # Query the 'enrichments' table.
        # Note: In a real scenario, we might need to join with a 'spans' table if 
        # file_path/start_line/end_line are stored there.
        # Based on current knowledge, 'enrichments' likely contains these or links to them.
        # We will assume a denormalized view or direct columns for simplicity based on SDD.
        # If columns are missing, this query will fail (and that's okay, we'll catch it).
        
        # Query the 'enrichments' table joined with 'spans' and 'files' to get location data.
        # This bridges the gap between Content Hash (DB) and Location (AST Graph).
        cursor.execute("""
            SELECT 
                e.span_hash, 
                e.summary, 
                e.usage_snippet,
                s.start_line,
                s.end_line,
                f.path as file_path
            FROM enrichments e
            JOIN spans s ON e.span_hash = s.span_hash
            JOIN files f ON s.file_id = f.id
        """)
        
        enrichments_by_span: Dict[str, List[EnrichmentRecord]] = {}
        for row in cursor.fetchall():
            # Convert row to dict
            row_dict = dict(row)
            
            record = EnrichmentRecord(
                span_hash=row_dict['span_hash'],
                file_path=row_dict['file_path'],
                start_line=row_dict['start_line'],
                end_line=row_dict['end_line'],
                summary=row_dict.get('summary'),
                usage_guide=row_dict.get('usage_snippet')
            )
            
            if record.span_hash:
                if record.span_hash not in enrichments_by_span:
                    enrichments_by_span[record.span_hash] = []
                enrichments_by_span[record.span_hash].append(record)

        conn.close()
        return enrichments_by_span
        
    except sqlite3.Error as e:
        # Log error? For now, return empty or partial results is safer than crashing
        print(f"Error loading enrichment DB: {e}")
        return {}
