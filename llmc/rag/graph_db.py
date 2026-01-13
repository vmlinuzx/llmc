from collections.abc import Iterable
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from .database import Database

logger = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS graph_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT,
    start_line INTEGER,
    end_line INTEGER,
    span_hash TEXT,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_name_lower ON nodes(lower(name));
CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_span_hash ON nodes(span_hash);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    type TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    migrated_at TEXT
);
"""

class Node(NamedTuple):
    id: str
    name: str
    path: str
    kind: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    span_hash: str | None = None
    metadata: dict[str, Any] | None = None

class Edge(NamedTuple):
    source: str
    target: str
    type: str
    metadata: dict[str, Any] | None = None

class GraphDatabase:
    def __init__(self, db_path: Path):
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._shared_conn: sqlite3.Connection | None = None

    def __enter__(self):
        if self._shared_conn is None:
            self._shared_conn = self._get_new_conn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._shared_conn:
            self._shared_conn.close()
            self._shared_conn = None

    def _init_db(self):
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    def _get_new_conn(self) -> sqlite3.Connection:
        """Open a new connection with FK enforcement."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # Enforce FK on every connection
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        """Return shared connection if in context, else a new one.
        
        If returning a new one, it is the caller's responsibility to close it,
        or use it in a 'with' block.
        """
        if self._shared_conn:
            return self._shared_conn
        return self._get_new_conn()

    def _get_conn(self) -> sqlite3.Connection:
        """Deprecated: Use self.conn instead."""
        return self.conn

    def bulk_insert_nodes(self, nodes: Iterable[Node]):
        # Use a dedicated connection for bulk ops to ensure commit
        with self._get_new_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO nodes (id, name, path, kind, start_line, end_line, span_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        n.id,
                        n.name,
                        n.path,
                        n.kind,
                        n.start_line,
                        n.end_line,
                        n.span_hash,
                        json.dumps(n.metadata) if n.metadata else None,
                    )
                    for n in nodes
                ),
            )
            conn.commit()

    def bulk_insert_edges(self, edges: Iterable[Edge]):
        with self._get_new_conn() as conn:
            conn.executemany(
                """
                INSERT INTO edges (source, target, type, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        e.source,
                        e.target,
                        e.type,
                        json.dumps(e.metadata) if e.metadata else None,
                    )
                    for e in edges
                ),
            )
            conn.commit()

    def vacuum(self):
        with self._get_new_conn() as conn:
            conn.execute("VACUUM")

    def node_count(self) -> int:
        if self._shared_conn:
            return self._shared_conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        with self._get_new_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def edge_count(self) -> int:
        if self._shared_conn:
            return self._shared_conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        with self._get_new_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    def get_node(self, node_id: str) -> Node | None:
        if self._shared_conn:
            row = self._shared_conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
            return self._row_to_node(row) if row else None
        with self._get_new_conn() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
            return self._row_to_node(row) if row else None

    def get_nodes_by_name(self, name: str, case_insensitive: bool = True) -> list[Node]:
        query = "SELECT * FROM nodes WHERE lower(name) = lower(?)" if case_insensitive else "SELECT * FROM nodes WHERE name = ?"
        if self._shared_conn:
            rows = self._shared_conn.execute(query, (name,)).fetchall()
            return [self._row_to_node(row) for row in rows]
        with self._get_new_conn() as conn:
            rows = conn.execute(query, (name,)).fetchall()
            return [self._row_to_node(row) for row in rows]

    def get_edges_from(self, source: str, edge_type: str | None = None) -> list[Edge]:
        query = "SELECT * FROM edges WHERE source = ?"
        params = [source]
        if edge_type:
            query += " AND type = ?"
            params.append(edge_type)
            
        if self._shared_conn:
            rows = self._shared_conn.execute(query, params).fetchall()
            return [self._row_to_edge(row) for row in rows]
        with self._get_new_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_edge(row) for row in rows]

    def get_edges_to(self, target: str, edge_type: str | None = None) -> list[Edge]:
        query = "SELECT * FROM edges WHERE target = ?"
        params = [target]
        if edge_type:
            query += " AND type = ?"
            params.append(edge_type)
            
        if self._shared_conn:
            rows = self._shared_conn.execute(query, params).fetchall()
            return [self._row_to_edge(row) for row in rows]
        with self._get_new_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_edge(row) for row in rows]

    def search_nodes(self, query: str, limit: int = 20) -> list[Node]:
        q = f"%{query}%"
        sql = "SELECT * FROM nodes WHERE name LIKE ? OR path LIKE ? LIMIT ?"
        params = (q, q, limit)
        if self._shared_conn:
            rows = self._shared_conn.execute(sql, params).fetchall()
            return [self._row_to_node(row) for row in rows]
        with self._get_new_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_node(row) for row in rows]

    def get_incoming_neighbors(self, target_names: list[str], edge_types: Iterable[str] | None = None) -> list[str]:
        """
        Get file paths of nodes that have edges pointing TO any node with a name in `target_names`.
        Equivalent to: "Who calls/uses these symbols?" (Upstream / Where Used)
        """
        if not target_names:
            return []
            
        name_placeholders = ",".join("?" * len(target_names))
        type_clause = ""
        type_params: list[str] = []
        if edge_types:
            types = list(edge_types)
            type_placeholders = ",".join("?" * len(types))
            type_clause = f"AND e.type IN ({type_placeholders})"
            type_params = types

        # Build suffix patterns ONLY for the edge target fallback (when node doesn't exist)
        # For the primary join, we rely on nodes.name and nodes.id indexes.
        suffix_patterns = []
        for name in target_names:
            suffix_patterns.append(f"%.{name}")
            suffix_patterns.append(f"%:{name}")
        
        edge_suffix_clause = " OR ".join(["e.target LIKE ?"] * len(suffix_patterns))
        node_suffix_clause = " OR ".join(["n_target.id LIKE ?"] * len(suffix_patterns))

        query = f"""
            SELECT DISTINCT path FROM (
                -- Match via node table (uses nodes.name and nodes.id indexes)
                SELECT n_src.path
                FROM nodes n_target
                JOIN edges e ON e.target = n_target.id
                JOIN nodes n_src ON e.source = n_src.id
                WHERE (
                    n_target.name IN ({name_placeholders}) 
                    OR n_target.id IN ({name_placeholders})
                    OR ({node_suffix_clause})
                )
                {type_clause}
                
                UNION
                
                -- Match directly on edge target (fallback for undefined target nodes)
                SELECT n_src.path
                FROM edges e
                JOIN nodes n_src ON e.source = n_src.id
                WHERE (
                    e.target IN ({name_placeholders})
                    OR ({edge_suffix_clause})
                )
                {type_clause}
            )
            WHERE path IS NOT NULL AND path != ''
            LIMIT 100
        """
        
        query_params = (
            list(target_names) + list(target_names) + suffix_patterns + type_params +
            list(target_names) + suffix_patterns + type_params
        )
            
        if self._shared_conn:
            rows = self._shared_conn.execute(query, query_params).fetchall()
            return [r["path"] for r in rows if r["path"]]
        with self._get_new_conn() as conn:
            rows = conn.execute(query, query_params).fetchall()
            return [r["path"] for r in rows if r["path"]]

    def get_outgoing_neighbors(self, source_names: list[str], edge_types: Iterable[str] | None = None) -> list[str]:
        """
        Get file paths of nodes targeted by edges FROM any node with a name in `source_names`.
        Equivalent to: "What do these symbols call/use?" (Downstream / Lineage)
        
        Supports exact name, exact ID, and suffix matches on ID.
        """
        if not source_names:
            return []

        conn = self._get_conn()
        try:
            name_placeholders = ",".join("?" * len(source_names))
            
            type_clause = ""
            type_params: list[str] = []
            if edge_types:
                types = list(edge_types)
                type_placeholders = ",".join("?" * len(types))
                type_clause = f"AND e.type IN ({type_placeholders})"
                type_params = types

            # Build suffix patterns for LIKE matching
            suffix_patterns = []
            for name in source_names:
                suffix_patterns.append(f"%.{name}")
                suffix_patterns.append(f"%:{name}")
            suffix_placeholders = " OR ".join(["n_source.id LIKE ?"] * len(suffix_patterns))

            # Join: nodes(source) -> edges -> nodes(target)
            query = f"""
                SELECT DISTINCT n_tgt.path
                FROM nodes n_source
                JOIN edges e ON e.source = n_source.id
                JOIN nodes n_tgt ON e.target = n_tgt.id
                WHERE (
                    n_source.name IN ({name_placeholders}) 
                    OR n_source.id IN ({name_placeholders})
                    OR ({suffix_placeholders})
                )
                {type_clause}
                LIMIT 100
            """
            
            # Param order: names (for name IN), names (for id IN), suffix patterns, types
            query_params = list(source_names) + list(source_names) + suffix_patterns + type_params

            rows = conn.execute(query, query_params).fetchall()
            return [r["path"] for r in rows if r["path"]]
        finally:
            if not self._shared_conn:
                conn.close()

    def get_file_neighbors(self, file_paths: list[str], limit: int = 20) -> list[str]:
        """
        Find files connected to the given seed files via any edge.
        Used for graph stitching/context expansion.
        """
        if not file_paths:
            return []

        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(file_paths))
            
            # 1. Find nodes belonging to seed files
            # 2. Find edges connected to those nodes (either direction)
            # 3. Find the path of the *other* node
            query = f"""
                SELECT DISTINCT n_other.path
                FROM nodes n_seed
                JOIN edges e ON (e.source = n_seed.id OR e.target = n_seed.id)
                JOIN nodes n_other ON (
                    CASE 
                        WHEN e.source = n_seed.id THEN e.target 
                        ELSE e.source 
                    END = n_other.id
                )
                WHERE n_seed.path IN ({placeholders})
                AND n_other.path NOT IN ({placeholders})
                LIMIT ?
            """
            params = file_paths + file_paths + [limit]
            rows = conn.execute(query, params).fetchall()
            return [r["path"] for r in rows if r["path"]]
        finally:
            if not self._shared_conn:
                conn.close()


    def get_meta(self, key: str) -> str | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM graph_meta WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None
        finally:
            if not self._shared_conn:
                conn.close()

    def is_stale(self, index_db: "Database") -> bool:
        """Return True if graph was built from older index data.
        
        Uses generation-based detection (preferred) with mtime+file_count fallback.
        This catches:
        - New/modified files (mtime increases)
        - Deleted files (file_count decreases)
        - Re-indexes (generation increments)
        """
        # Preferred: generation-based staleness (if present)
        stored_gen = self.get_meta("index_generation")
        if stored_gen is not None:
            try:
                current_gen = index_db.conn.execute(
                    "SELECT value FROM llmc_meta WHERE key = 'index_generation'"
                ).fetchone()
                if current_gen and int(current_gen[0]) != int(stored_gen):
                    return True
                # Generation matches, graph is fresh
                if current_gen:
                    return False
            except Exception:
                pass  # Fall through to mtime check
        
        # Fallback: mtime + file_count (catches deletes that mtime misses)
        stored_mtime = self.get_meta("index_db_mtime")
        stored_file_count = self.get_meta("index_file_count")
        
        if not stored_mtime:
            return True
            
        try:
            stored_ts = float(stored_mtime)
        except (ValueError, TypeError):
            return True

        current_mtime = index_db.conn.execute(
            "SELECT MAX(mtime) FROM files"
        ).fetchone()[0]
        
        # Check if mtime is stale
        if stored_ts < (current_mtime or 0):
            return True
        
        # Check if file count changed (catches deletes)
        if stored_file_count:
            try:
                current_count = index_db.conn.execute(
                    "SELECT COUNT(*) FROM files"
                ).fetchone()[0]
                if int(stored_file_count) != current_count:
                    return True
            except Exception:
                pass
        
        return False

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            kind=row["kind"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            span_hash=row["span_hash"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge(
            source=row["source"],
            target=row["target"],
            type=row["type"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )


def build_from_json(repo_root: Path) -> GraphDatabase:
    """Build SQLite graph database from JSON artifact.
    
    Reads `.llmc/rag_graph.json` and populates `.llmc/rag_graph.db`.
    Returns the database instance for immediate use.
    
    This is the bridge between the legacy JSON pipeline and the new
    O(1) SQLite query path.
    """
    json_path = repo_root / ".llmc" / "rag_graph.json"
    db_path = repo_root / ".llmc" / "rag_graph.db"
    
    if not json_path.is_file():
        raise FileNotFoundError(f"No graph JSON found: {json_path}")
    
    # Read JSON graph
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid graph format in {json_path}")
    
    # Handle nested schema_graph wrapper
    if isinstance(raw.get("schema_graph"), dict):
        raw = raw["schema_graph"]
    
    # Extract nodes
    raw_nodes = raw.get("nodes") or raw.get("vertices") or raw.get("entities") or []
    raw_edges = raw.get("edges") or raw.get("links") or raw.get("relations") or []
    
    def _norm_path(p: str) -> str:
        if not p:
            return ""
        return str(Path(p.split(":", 1)[0]).as_posix())
    
    def _extract_name(node: dict) -> str:
        """Extract short symbol name for indexing."""
        raw_name = str(node.get("name") or node.get("id") or "")
        # Extract leaf name from qualified path like "pkg.mod.func" or "mod:func"
        if ":" in raw_name:
            raw_name = raw_name.split(":")[-1]
        if "." in raw_name:
            raw_name = raw_name.split(".")[-1]
        return raw_name
    
    # Convert to Node objects
    nodes = []
    for n in raw_nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or n.get("nid") or n.get("name") or "")
        if not nid:
            continue
        
        path = _norm_path(
            n.get("file_path") or n.get("path") or n.get("file") or ""
        )
        name = _extract_name(n)
        kind = n.get("kind") or n.get("type")
        
        span = n.get("span") or n.get("loc") or {}
        start_line = span.get("start_line") or span.get("start") or n.get("start_line")
        end_line = span.get("end_line") or span.get("end") or n.get("end_line")
        
        metadata = n.get("metadata")
        span_hash = (metadata or {}).get("span_hash") if metadata else None
        
        nodes.append(Node(
            id=nid,
            name=name,
            path=path,
            kind=kind,
            start_line=int(start_line) if start_line else None,
            end_line=int(end_line) if end_line else None,
            span_hash=span_hash,
            metadata=metadata,
        ))
    
    # Convert to Edge objects
    edges = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        
        etype = str(e.get("type") or e.get("edge") or e.get("label") or "").upper()
        src = str(e.get("source") or e.get("src") or e.get("from") or "")
        dst = str(e.get("target") or e.get("dst") or e.get("to") or "")
        
        if not src or not dst:
            continue
        
        edges.append(Edge(source=src, target=dst, type=etype))
    
    # Generate stub nodes for external references (fixes FK constraint failures)
    # Edges may reference stdlib/external symbols that don't have entity nodes
    node_ids = {n.id for n in nodes}
    missing_ids = set()
    for e in edges:
        if e.source not in node_ids:
            missing_ids.add(e.source)
        if e.target not in node_ids:
            missing_ids.add(e.target)
    
    if missing_ids:
        logger.info(
            "Creating %d stub nodes for external references",
            len(missing_ids)
        )
        for mid in missing_ids:
            # Extract leaf name from qualified ID like "sym:mod.func" or "sym:mod:Class.method"
            leaf = mid
            if ":" in leaf:
                leaf = leaf.split(":")[-1]
            if "." in leaf:
                leaf = leaf.split(".")[-1]
            
            nodes.append(Node(
                id=mid,
                name=leaf,
                path="<external>",
                kind="external",
                start_line=None,
                end_line=None,
                span_hash=None,
                metadata={"stub": True, "original_id": mid},
            ))
    
    # Remove existing database and create fresh
    if db_path.exists():
        db_path.unlink()

    # Get metadata from index for staleness detection
    index_path = repo_root / ".llmc" / "rag" / "index_v2.db"
    max_mtime = 0.0
    file_count = 0
    index_generation = None
    
    if index_path.exists():
        try:
            with sqlite3.connect(index_path) as idx_conn:
                # Get max mtime
                row = idx_conn.execute("SELECT MAX(mtime) FROM files").fetchone()
                if row and row[0]:
                    max_mtime = float(row[0])
                
                # Get file count (to detect deletes)
                count_row = idx_conn.execute("SELECT COUNT(*) FROM files").fetchone()
                if count_row:
                    file_count = count_row[0]
                
                # Try to get generation (if llmc_meta table exists)
                try:
                    gen_row = idx_conn.execute(
                        "SELECT value FROM llmc_meta WHERE key = 'index_generation'"
                    ).fetchone()
                    if gen_row:
                        index_generation = gen_row[0]
                except sqlite3.OperationalError:
                    pass  # llmc_meta table doesn't exist yet
        except Exception:
            pass  # If index is busy or broken, use defaults (will be stale)

    db = GraphDatabase(db_path)
    db.bulk_insert_nodes(nodes)
    db.bulk_insert_edges(edges)
    
    # Write staleness metadata
    with db._get_new_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO graph_meta (key, value) VALUES (?, ?)",
            ("index_db_mtime", str(max_mtime))
        )
        conn.execute(
            "INSERT OR REPLACE INTO graph_meta (key, value) VALUES (?, ?)",
            ("index_file_count", str(file_count))
        )
        if index_generation is not None:
            conn.execute(
                "INSERT OR REPLACE INTO graph_meta (key, value) VALUES (?, ?)",
                ("index_generation", str(index_generation))
            )
        conn.execute(
            "INSERT OR REPLACE INTO graph_meta (key, value) VALUES (?, ?)",
            ("built_at", datetime.now(UTC).isoformat())
        )
        conn.commit()
    
    # Audit span_hash coverage
    with db._get_new_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        linked = conn.execute("SELECT COUNT(*) FROM nodes WHERE span_hash IS NOT NULL").fetchone()[0]
        if total > 0:
            logger.info(
                "Graph integrity: %d/%d nodes linked to index (%.1f%%)",
                linked,
                total,
                (linked / total * 100),
            )

    db.vacuum()
    
    return db

