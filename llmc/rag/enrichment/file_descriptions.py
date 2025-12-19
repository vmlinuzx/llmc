"""
File Description Generator

This module provides functions for generating file-level descriptions from span enrichments.
"""

from __future__ import annotations

from typing import Any

from llmc.rag.database import Database

def generate_cheap_description(db: Database, file_path: str) -> str | None:
    """
    Generates a file description by concatenating the summaries of its most important spans.
    """
    # This is a simplified implementation. A real implementation would need to
    # identify the most "important" spans (e.g., class docstrings, module-level
    # docstrings, key functions) and concatenate their summaries.
    # For now, we'll just grab the first 5 summaries for a given file.

    rows = db.conn.execute(
        """
        SELECT e.summary
        FROM enrichments e
        JOIN spans s ON e.span_hash = s.span_hash
        JOIN files f ON s.file_id = f.id
        WHERE f.path = ? AND e.summary IS NOT NULL
        ORDER BY s.start_line
        LIMIT 5
        """,
        (file_path,),
    ).fetchall()

    if not rows:
        return None

    summaries = [row[0] for row in rows]
    return " ".join(summaries)


def generate_rich_description(db: Database, file_path: str) -> str | None:
    """
    Generates a file description using an LLM to summarize the file's purpose.
    (Placeholder for future implementation)
    """
    # In a real implementation, this function would:
    # 1. Read the file content.
    # 2. Pass the content to an LLM with a prompt asking for a high-level summary.
    # 3. Return the LLM's response.
    return None

def update_file_description(db: Database, file_path: str, content_hash: str) -> None:
    """
    Updates the file description in the database.
    """
    description = generate_cheap_description(db, file_path)
    if description:
        file_id_row = db.conn.execute("SELECT id FROM files WHERE path = ?", (file_path,)).fetchone()
        if not file_id_row:
            return
        file_id = file_id_row[0]

        db.conn.execute(
            """
            INSERT OR REPLACE INTO file_descriptions (file_id, file_path, description, source, updated_at, content_hash)
            VALUES (?, ?, ?, ?, strftime('%s','now'), ?)
            """,
            (file_id, file_path, description, "cheap", content_hash),
        )
        db.conn.commit()
