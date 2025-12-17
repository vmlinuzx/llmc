"""Query History & Analytics

Track search queries and provide insights for context optimization.

Features:
- Query logging with timestamps
- Most searched terms analysis
- Frequently retrieved files
- Analytics dashboard in TUI
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


@dataclass
class QueryRecord:
    """A recorded search query."""

    query_text: str
    timestamp: datetime
    results_count: int
    files_retrieved: list[str]


@dataclass
class AnalyticsSummary:
    """Summary of analytics over a time period."""

    top_queries: list[tuple[str, int]]  # (query, count)
    top_files: list[tuple[str, int]]  # (file, count)
    total_queries: int
    unique_queries: int
    avg_results_per_query: float
    time_range_days: int


class QueryTracker:
    """Tracks and analyzes search queries."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS query_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_text TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        results_count INTEGER NOT NULL,
        files_retrieved TEXT  -- JSON array of file paths
    );
    
    CREATE INDEX IF NOT EXISTS idx_query_timestamp ON query_history(timestamp);
    CREATE INDEX IF NOT EXISTS idx_query_text ON query_history(query_text);
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Initialize analytics database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(self.SCHEMA)
        conn.close()

    def log_query(
        self, query_text: str, results_count: int, files_retrieved: list[str]
    ):
        """Log a search query."""
        import json

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT INTO query_history (query_text, results_count, files_retrieved)
            VALUES (?, ?, ?)
            """,
            (query_text, results_count, json.dumps(files_retrieved)),
        )
        conn.commit()
        conn.close()

    def get_analytics(self, days: int = 7) -> AnalyticsSummary:
        """Get analytics summary for the last N days."""
        import json

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        # Get top queries
        cursor = conn.execute(
            """
            SELECT query_text, COUNT(*) as count
            FROM query_history
            WHERE timestamp >= ?
            GROUP BY query_text
            ORDER BY count DESC
            LIMIT 10
            """,
            (cutoff_str,),
        )
        top_queries = [(row["query_text"], row["count"]) for row in cursor]

        # Get top files
        cursor = conn.execute(
            """
            SELECT files_retrieved
            FROM query_history
            WHERE timestamp >= ?
            """,
            (cutoff_str,),
        )

        file_counts: dict[str, int] = {}
        for row in cursor:
            try:
                files = json.loads(row["files_retrieved"])
                for file in files:
                    file_counts[file] = file_counts.get(file, 0) + 1
            except Exception:
                pass

        top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Get overall stats
        cursor = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT query_text) as unique_queries,
                AVG(results_count) as avg_results
            FROM query_history
            WHERE timestamp >= ?
            """,
            (cutoff_str,),
        )
        row = cursor.fetchone()

        conn.close()

        return AnalyticsSummary(
            top_queries=top_queries,
            top_files=top_files,
            total_queries=row["total"],
            unique_queries=row["unique_queries"],
            avg_results_per_query=round(row["avg_results"] or 0, 1),
            time_range_days=days,
        )

    def get_recent_queries(self, limit: int = 20) -> list[QueryRecord]:
        """Get recent queries."""
        import json

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            """
            SELECT query_text, timestamp, results_count, files_retrieved
            FROM query_history
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        records = []
        for row in cursor:
            try:
                files = json.loads(row["files_retrieved"])
            except Exception:
                files = []

            records.append(
                QueryRecord(
                    query_text=row["query_text"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    results_count=row["results_count"],
                    files_retrieved=files,
                )
            )

        conn.close()
        return records


def format_analytics(summary: AnalyticsSummary) -> str:
    """Format analytics summary as human-readable string."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"QUERY ANALYTICS (Last {summary.time_range_days} Days)")
    lines.append("=" * 60)
    lines.append(f"Total Queries: {summary.total_queries}")
    lines.append(f"Unique Queries: {summary.unique_queries}")
    lines.append(f"Avg Results/Query: {summary.avg_results_per_query}")
    lines.append("")

    if summary.top_queries:
        lines.append("TOP QUERIES:")
        for i, (query, count) in enumerate(summary.top_queries, 1):
            # Truncate long queries
            display_query = query if len(query) <= 50 else query[:47] + "..."
            lines.append(f"  {i:2}. {display_query:50} ({count} searches)")
        lines.append("")

    if summary.top_files:
        lines.append("MOST RETRIEVED FILES:")
        for i, (file, count) in enumerate(summary.top_files, 1):
            # Show just filename if path is long
            display_file = file if len(file) <= 50 else "..." + file[-47:]
            lines.append(f"  {i:2}. {display_file:50} ({count} times)")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def run_analytics(repo_root: Path, days: int = 7):
    """Run analytics and print report."""
    analytics_db = repo_root / ".rag" / "analytics.db"

    if not analytics_db.parent.exists():
        print("No query history found. Start searching to build analytics!")
        return

    tracker = QueryTracker(analytics_db)
    summary = tracker.get_analytics(days=days)

    print(format_analytics(summary))


if __name__ == "__main__":
    import argparse

    from .utils import find_repo_root

    parser = argparse.ArgumentParser(description="View query analytics")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days to analyze")
    parser.add_argument("--repo", type=Path, help="Repository root path")

    args = parser.parse_args()

    repo = args.repo or find_repo_root()
    run_analytics(repo, days=args.days)
