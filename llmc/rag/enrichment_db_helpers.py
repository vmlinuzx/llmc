from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from llmc.rag.config import index_path_for_read, rag_dir
from llmc.rag.database import Database


@dataclass
class EnrichmentRecord:
    # Matches structure of 'enrichments' table and relevant 'spans' columns
    span_hash: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    summary: str | None = None
    usage_guide: str | None = None
    # Additional fields can be added here as needed (inputs, outputs, etc.)
    # For now, we focus on the core ones defined in SDD


def _candidate_db_paths(repo_root: Path) -> list[Path]:
    """Return enrichment DB candidates ordered by priority."""
    candidates = [
        repo_root / ".llmc" / "rag" / "enrichment.db",
        repo_root / ".llmc" / "rag" / "index_v2.db",
        rag_dir(repo_root) / "enrichment.db",
        rag_dir(repo_root) / "index_v2.db",
        index_path_for_read(repo_root),
    ]
    unique: list[Path] = []
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def get_enrichment_db_path(repo_root: Path) -> Path:
    """Returns the path to the enrichment database for a given repo."""
    for candidate in _candidate_db_paths(repo_root):
        if candidate.exists():
            return candidate
    # Fallback to default index path even if it doesn't exist yet
    return index_path_for_read(repo_root)


def load_enrichment_data(repo_root: Path) -> dict[str, list[EnrichmentRecord]]:
    """
    Loads all enrichment data from the SQLite DB for a repo.
    Returns a dict mapping span_hash to a list of EnrichmentRecords.
    """
    db_path = get_enrichment_db_path(repo_root)
    if not db_path.exists():
        return {}

    try:
        enrichments_by_span: dict[str, list[EnrichmentRecord]] = {}
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            tables = {
                row[0]
                for row in cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            enrichment_columns = {
                row[1] for row in cursor.execute("PRAGMA table_info(enrichments)")
            }
            usage_column = None
            if "usage_snippet" in enrichment_columns:
                usage_column = "usage_snippet"
            elif "usage_guide" in enrichment_columns:
                usage_column = "usage_guide"

            rows = []
            if {"spans", "files"}.issubset(tables):
                usage_expr = (
                    f"e.{usage_column} AS usage_text"
                    if usage_column
                    else "NULL AS usage_text"
                )
                query = f"""
                    SELECT 
                        e.span_hash, 
                        e.summary, 
                        {usage_expr},
                        s.start_line,
                        s.end_line,
                        f.path as file_path
                    FROM enrichments e
                    JOIN spans s ON e.span_hash = s.span_hash
                    JOIN files f ON s.file_id = f.id
                """
                rows = cursor.execute(query).fetchall()
            else:
                select_parts = ["span_hash"]
                for col in ("file_path", "start_line", "end_line", "summary"):
                    if col in enrichment_columns:
                        select_parts.append(col)
                if usage_column:
                    select_parts.append(f"{usage_column} AS usage_text")
                query = f"SELECT {', '.join(select_parts)} FROM enrichments"
                rows = cursor.execute(query).fetchall()

            for row in rows:
                row_dict = dict(row)
                record = EnrichmentRecord(
                    span_hash=row_dict.get("span_hash", ""),
                    file_path=row_dict.get("file_path"),
                    start_line=row_dict.get("start_line"),
                    end_line=row_dict.get("end_line"),
                    summary=row_dict.get("summary"),
                    usage_guide=row_dict.get("usage_text")
                    or row_dict.get("usage_snippet")
                    or row_dict.get("usage_guide"),
                )

                if not record.span_hash:
                    continue
                enrichments_by_span.setdefault(record.span_hash, []).append(record)

        return enrichments_by_span

    except sqlite3.Error as e:
        print(f"Error loading enrichment DB: {e}")
        return {}


def write_enrichment(
    db: Database,
    span_hash: str,
    summary: str,
    key_topics: list[str] | None = None,
    complexity: str | None = None,
    model: str | None = None,
) -> None:
    """Write enrichment result to database."""
    payload: dict[str, Any] = {
        "summary_120w": summary,
        "model": model,
        "tags": key_topics or [],
    }
    if complexity:
        payload["tags"].append(f"complexity:{complexity}")

    db.store_enrichment(span_hash, payload)
