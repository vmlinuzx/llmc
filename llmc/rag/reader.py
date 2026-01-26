"""
Reader Module for LLMC RAG

Provides functionality to read specific code blocks based on symbol lookups
in the LSP Graph database.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from .graph_db import GraphDatabase


class CodeSpan(NamedTuple):
    file_path: Path
    start_line: int
    end_line: int
    content: str
    symbol: str

def read_implementation(repo_root: Path, symbol: str) -> CodeSpan | None:
    """
    Finds and reads the implementation code for a given symbol.
    
    Args:
        repo_root: Root of the repository.
        symbol: The symbol identifier (e.g., 'llmc.rag.graph_db.GraphDatabase').
                Accepts partial matches if unique, or full matches.
                Tries 'sym:' and 'type:' prefixes if not provided.

    Returns:
        CodeSpan object containing the code and location, or None if not found.
    """
    db_path = repo_root / ".llmc" / "rag_graph.db"
    if not db_path.exists():
        # Fallback to json if db doesn't exist? No, we require DB for this precision.
        return None

    # We need to find the node.
    # The graph_db.py doesn't expose a simple "find by symbol name" for public use comfortably?
    # It has search_nodes(query) and get_nodes_by_name(name).
    
    with GraphDatabase(db_path) as db:
        # 1. Try exact match assuming it's a fully qualified ID (minus prefix)
        # IDs are like 'sym:module.func' or 'type:module.Class'
        
        # Try finding by name first (fastest index)
        # symbol might be "GraphDatabase" or "llmc.rag.graph_db.GraphDatabase"
        
        # Strategy:
        # A. Exact ID match (if user provided 'sym:...')
        node = db.get_node(symbol)
        if node:
             return _read_span(repo_root, node)
             
        # B. Exact ID match with prefixes
        node = db.get_node(f"sym:{symbol}")
        if node:
            return _read_span(repo_root, node)
            
        node = db.get_node(f"type:{symbol}")
        if node:
            return _read_span(repo_root, node)

        # C. Try searching for the symbol ending with the query (e.g. "GraphDatabase.bulk_insert_nodes")
        # The 'id' column contains the full symbol.
        # We can use LIKE %symbol in SQL via search_nodes (which does name LIKE ?)
        # But search_nodes matches 'name' column.
        # If I search for 'GraphDatabase.bulk_insert_nodes', name is likely just 'bulk_insert_nodes', so name search won't work well if I qualify it.
        
        # We need a way to search 'id' or handle the qualification.
        # Let's try raw query for ID suffix
        cursor = db.conn.execute("SELECT id FROM nodes WHERE id LIKE ?", (f"%{symbol}",))
        matches = cursor.fetchall()
        if len(matches) == 1:
            node = db.get_node(matches[0][0])
            if node:
                return _read_span(repo_root, node)
        
        # D. Search by Name (short name)
        # ...
        # The 'name' column in nodes table is usually the short name? 
        # schema.py says: symbol = f"{self.module_name}.{node.name}"
        # Entity id is sym:symbol.
        # But node.name in the DB might just be the short name?
        # Let's check schema.py: 
        #   entity = Entity(id=entity_id, kind="class", path=..., metadata=...)
        #   graph_db.py: bulk_insert_nodes -> 'name' is derived from entity.id?
        #   Actually graph_db.py build_from_json uses:
        #   name=val.get("name") or val["id"].split(".")[-1]
        
        # So 'name' in DB is likely short name. 'id' is full name.
        
        # So if the user gives "llmc.rag.graph_db.GraphDatabase":
        # It should match 'type:llmc.rag.graph_db.GraphDatabase' ID.
        
        # What if user gives "GraphDatabase"?
        # select * from nodes where name = ?
        nodes = db.get_nodes_by_name(symbol)
        if len(nodes) == 1:
            return _read_span(repo_root, nodes[0])
        elif len(nodes) > 1:
            # Ambiguous. Return the one that matches partial path?
            # For now, just return None or raise? 
            # Let's return the first one but maybe warn? 
            # Simple heuristic: Prefer the one with shortest path or specialized logic?
            # Let's just return the first one for the "Sniper" tool.
            return _read_span(repo_root, nodes[0])
            
    return None

def _read_span(repo_root: Path, node: Any) -> CodeSpan:
    # node has .path which is "absolute_path:start-end" or relative?
    # schema.py stores: path=f"{self.file_path}:{node.lineno}-{node.end_lineno}"
    # and file_path is absolute.
    
    # But graph_db.py Nodes table path column:
    # "path TEXT NOT NULL"
    
    # The path provided in node.path is the file path (relative or absolute).
    # The start_line and end_line are separate columns in the node object (NamedTuple from graph_db).
    
    file_part = node.path
    start_line = node.start_line or 0
    end_line = node.end_line or 0
    
    # If the path actually has :start-end attached (legacy?)
    if ":" in str(file_part):
        # It shouldn't if we use the graph payload correctly, but let's be safe
        # In schema.py: path=f"{self.file_path}:{node.lineno}-{node.end_lineno}"
        # BUT this is the 'path' field in Entity.
        # When inserted into DB:
        # bulk_insert_nodes uses: (e.id, ... e.path ...)
        # So yes, the DB's 'path' column contains "loc:10-20".
        # However, start_line/end_line columns also exist?
        pass

    # Wait, in the CLI output I saw:
    # sym:graph_db.GraphDatabase.bulk_insert_nodes|...|llmc/rag/graph_db.py|function|116|138|...
    # The path column is JUST the file path: "llmc/rag/graph_db.py"
    # The line numbers are in start_line (116) and end_line (138).
    
    # So I WAS WRONG to assume parsing `node.path` for line numbers is primary.
    # The DB schema has separate columns.


    file_path = Path(file_part)
    
    if not file_path.exists():
        # Maybe it's relative to repo root?
        file_path = repo_root / file_part
    
    if not file_path.exists():
         return CodeSpan(file_path, start_line, end_line, "# File not found", node.id)

    lines = file_path.read_text(encoding="utf-8").splitlines()
    
    # Lines are 1-indexed
    # Slice: start_line-1 to end_line
    # Safety checks
    if start_line < 1: start_line = 1
    if end_line > len(lines): end_line = len(lines)
    
    snippet = "\n".join(lines[start_line-1 : end_line])
    
    return CodeSpan(
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        content=snippet,
        symbol=node.id
    )
