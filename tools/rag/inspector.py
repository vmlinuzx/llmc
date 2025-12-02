from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
from typing import Any, Literal

from . import database as rag_database
from .config import index_path_for_read
from .schema import SchemaGraph

SourceMode = Literal["symbol", "file"]

@dataclass
class RelatedEntity:
    symbol: str
    path: str

@dataclass
class DefinedSymbol:
    name: str
    line: int
    type: str
    summary: str | None = None

@dataclass
class InspectionResult:
    path: str
    source_mode: SourceMode
    
    snippet: str
    full_source: str | None
    primary_span: tuple[int, int] | None
    file_summary: str | None
    
    graph_status: str = "unknown"  # graph_missing, file_not_indexed, isolated, connected
    
    defined_symbols: list[DefinedSymbol] = field(default_factory=list)
    
    parents: list[RelatedEntity] = field(default_factory=list)
    children: list[RelatedEntity] = field(default_factory=list)
    incoming_calls: list[RelatedEntity] = field(default_factory=list)
    outgoing_calls: list[RelatedEntity] = field(default_factory=list)
    related_tests: list[RelatedEntity] = field(default_factory=list)
    related_docs: list[RelatedEntity] = field(default_factory=list)
    
    enrichment: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _normalize_path(repo_root: Path, target: str) -> Path:
    """Resolve target path relative to repo root, with fuzzy suffix matching."""
    # 1. Try as exact path (relative or absolute)
    p = Path(target)
    if p.is_absolute():
        try:
            return p.relative_to(repo_root)
        except ValueError:
            pass # Not inside repo, might be fine if exists, but we prefer repo-rel
    
    full_path = repo_root / target
    if full_path.exists():
        return Path(target)

    # 2. Fuzzy Suffix Match
    # Find files in repo that end with the target string
    # This is a simple heuristic: find 'router.py' -> 'scripts/router.py'
    matches = []
    target_name = p.name
    
    # Walk repo (skip hidden/venv)
    for file in repo_root.rglob(f"*{target_name}"):
        if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules") for part in file.parts):
            continue
        
        if str(file).endswith(target):
            try:
                matches.append(file.relative_to(repo_root))
            except ValueError:
                pass
    
    if not matches:
        return p # Return original to fail downstream or be handled as symbol

    # Sort matches: shortest path length first, then alphabetical
    matches.sort(key=lambda m: (len(m.parts), str(m)))
    
    return matches[0]

def _read_file_content(repo_root: Path, rel_path: Path) -> str:
    full_path = repo_root / rel_path
    if not full_path.exists():
        return ""
    return full_path.read_text(encoding="utf-8", errors="replace")

def _extract_snippet(lines: list[str], span: tuple[int, int] | None, context: int = 5, max_lines: int = 50) -> str:
    """Extract a focused snippet around the span."""
    if not lines:
        return ""
    
    if not span:
        # Default file snippet: header + first N lines
        return "\n".join(lines[:max_lines])
    
    start, end = span
    # 1-based to 0-based
    start_idx = max(0, start - 1 - context)
    end_idx = min(len(lines), end + context)
    
    snippet_lines = lines[start_idx:end_idx]
    if len(snippet_lines) > max_lines:
        # Truncate center if too long? For now just take the top chunk
        snippet_lines = snippet_lines[:max_lines]
        snippet_lines.append("... (truncated)")
        
    return "\n".join(snippet_lines)

def _get_provenance(repo_root: Path, rel_path: Path) -> dict[str, Any]:
    prov = {
        "kind": "code", # simplistic default
        "last_commit": None,
        "last_commit_date": None,
        "indexed_at": None
    }
    
    # Heuristic for kind
    p_str = str(rel_path)
    if "test" in p_str:
        prov["kind"] = "test"
    elif "docs" in p_str.lower() or p_str.endswith(".md"):
        prov["kind"] = "docs"
    
    # Git info
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h %cs", "--", str(rel_path)],
            check=False, cwd=repo_root, capture_output=True, text=True, timeout=1
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split()
            if len(parts) >= 2:
                prov["last_commit"] = parts[0]
                prov["last_commit_date"] = parts[1]
    except Exception:
        pass
        
    return prov

def _fetch_enrichment(
    db_path: Path, 
    span_hash: str | None, 
    symbol: str | None = None, 
    file_path: Path | None = None
) -> dict[str, Any]:
    data = {
        "summary": None, "inputs": None, "outputs": None, 
        "side_effects": None, "pitfalls": None, "evidence_count": None
    }
    if not db_path.exists():
        return data

    db = rag_database.Database(db_path)
    try:
        row = None
        # 1. Try exact hash lookup
        if span_hash:
            row = db.conn.execute(
                "SELECT summary, inputs, outputs, side_effects, pitfalls, evidence FROM enrichments WHERE span_hash = ?",
                (span_hash,)
            ).fetchone()
        
        # 2. Fallback: Fuzzy match by path and symbol
        if not row and symbol and file_path:
            # We need to match file path suffix because DB paths might be relative or absolute
            # and symbol might be short or fully qualified.
            
            # Try to find short symbol name
            short_sym = symbol.split(".")[-1]
            path_suffix = f"%{file_path}"
            
            query = """
                SELECT e.summary, e.inputs, e.outputs, e.side_effects, e.pitfalls, e.evidence
                FROM enrichments e
                JOIN spans s ON e.span_hash = s.span_hash
                JOIN files f ON s.file_id = f.id
                WHERE f.path LIKE ? AND (s.symbol = ? OR s.symbol LIKE ?)
                LIMIT 1
            """
            # Try exact symbol match first, then fuzzy
            row = db.conn.execute(query, (path_suffix, short_sym, f"%{short_sym}")).fetchone()

        if row:
            data["summary"] = row["summary"]
            # Attempt JSON decode for lists
            for key in ["inputs", "outputs", "side_effects", "pitfalls"]:
                if row[key]:
                    try:
                        data[key] = json.loads(row[key])
                    except:
                        data[key] = row[key]
            
            if row["evidence"]:
                try:
                    ev = json.loads(row["evidence"])
                    data["evidence_count"] = len(ev)
                except:
                    pass
    except Exception:
        pass
    finally:
        db.close()
    return data

def inspect_entity(
    repo_root: Path,
    *,
    symbol: str | None = None,
    path: str | None = None,
    line: int | None = None,
    include_full_source: bool = False,
    max_neighbors: int = 3,
) -> InspectionResult:
    """Resolve a symbol or file location, aggregate graph + enrichment + provenance."""
    
    # 1. Load Graph (lazy load could be optimized later)
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    graph = None
    graph_status = "graph_missing"
    
    if graph_path.exists():
        try:
            graph = SchemaGraph.load(graph_path)
            graph_status = "loaded"
        except:
            pass

    # 2. Resolve Target
    target_entity = None
    rel_path = None
    
    if symbol and graph:
        # Try direct symbol match
        # SchemaGraph entities have 'id', usually "kind:symbol" or just "symbol" depending on version
        # The indexer uses "kind:module.name". Let's try fuzzy match if exact fails.
        
        # First, exact ID match attempt (rarely works without prefix)
        # Then suffix match
        candidates = []
        for ent in graph.entities:
            # Entity ID format: "func:src.main.main_func"
            # We want to match "src.main.main_func"
            ent_name = ent.id.split(":", 1)[-1]
            if ent_name == symbol or ent_name.endswith(f".{symbol}"):
                candidates.append(ent)
        
        if candidates:
            # Pick best match? For now first.
            target_entity = candidates[0]
            rel_path = Path(target_entity.file_path) if target_entity.file_path else None

    if not target_entity and path:
        # File mode
        rel_path = _normalize_path(repo_root, path)
        
        if line and graph:
            # Try to find entity covering line
            # Using schema 2.0 fields start_line/end_line
            for ent in graph.entities:
                # Normalize entity path for matching
                ent_path = Path(ent.file_path) if ent.file_path else None
                if ent_path == rel_path:
                    if ent.start_line and ent.end_line:
                        if ent.start_line <= line <= ent.end_line:
                            target_entity = ent
                            break
    
    # If still no rel_path derived from symbol, fail?
    if not rel_path and not target_entity:
        # Cannot resolve
        # In a real implementation we might fuzzy search files. 
        # For now, return empty result or raise.
        # Let's handle the case where user passes a path that isn't in the graph
        if path:
            rel_path = _normalize_path(repo_root, path)
        else:
             raise ValueError("Could not resolve symbol or path.")

    source_content = _read_file_content(repo_root, rel_path)
    source_lines = source_content.splitlines()
    
    mode: SourceMode = "symbol" if target_entity else "file"
    
    # 3. Build Snippet
    primary_span = None
    if target_entity and target_entity.start_line and target_entity.end_line:
        primary_span = (target_entity.start_line, target_entity.end_line)
    
    snippet = _extract_snippet(source_lines, primary_span)
    
    # 4. Gather Graph Context
    defined_syms = []
    parents = []
    children = []
    in_calls = []
    out_calls = []
    tests = []
    docs = []
    file_entities = []
    
    if graph:
        # Check if file is in graph at all
        file_entities = [e for e in graph.entities if e.file_path == str(rel_path)]
        
        if not file_entities:
            graph_status = "file_not_indexed"
        else:
            # Defined symbols in this file
            # Sort by line
            file_entities.sort(key=lambda x: x.start_line or 0)
            
            for ent in file_entities[:10]: # Limit to 10
                 name = ent.id.split(":", 1)[-1].split(".")[-1]
                 defined_syms.append(DefinedSymbol(
                     name=name,
                     line=ent.start_line or 0,
                     type=ent.kind,
                     summary=ent.metadata.get("summary")
                 ))

            # Aggregate relationships
            # If target_entity set, we focus on that.
            # If not (File Mode), we aggregate ALL entities in the file.
            
            focus_entities = [target_entity] if target_entity else file_entities
            focus_ids = {e.id for e in focus_entities}
            
            # Use sets for deduplication before converting to RelatedEntity
            s_parents = set()
            s_children = set()
            s_in_calls = set()
            s_out_calls = set()
            s_tests = set()
            s_docs = set()
            
            # Helper to resolving entity ID to (symbol, path)
            def resolve_ent(eid: str) -> tuple[str, str]:
                e = next((x for x in graph.entities if x.id == eid), None)
                if e:
                    # Clean symbol name
                    sym = e.id.split(":", 1)[-1]
                    return sym, (e.file_path or "")
                return eid, ""

            for rel in graph.relations:
                # Outgoing: focus -> other
                if rel.src in focus_ids:
                    if rel.dst in focus_ids:
                        continue # Internal self-reference within file/selection
                    
                    sym, p = resolve_ent(rel.dst)
                    if rel.edge == "calls":
                        s_out_calls.add((sym, p))
                    elif rel.edge == "extends":
                        s_parents.add((sym, p))
                
                # Incoming: other -> focus
                elif rel.dst in focus_ids:
                    if rel.src in focus_ids:
                        continue
                        
                    sym, p = resolve_ent(rel.src)
                    if rel.edge == "calls":
                        s_in_calls.add((sym, p))
                    elif rel.edge == "extends":
                        s_children.add((sym, p))
                    elif "test" in rel.src.lower() or rel.edge == "tests":
                        s_tests.add((sym, p))
                    elif rel.edge == "documents": # hypothetical
                        s_docs.add((sym, p))
            
            # Convert sets to lists
            def to_list(s):
                return [RelatedEntity(symbol=x[0], path=x[1]) for x in sorted(list(s))]

            parents = to_list(s_parents)
            children = to_list(s_children) # Children usually imply nested structure, simplistic graph usually doesn't explicitly link file->class via 'edge', but we leave empty for now unless we parse structure.
            in_calls = to_list(s_in_calls)
            out_calls = to_list(s_out_calls)
            tests = to_list(s_tests)
            docs = to_list(s_docs)
            
            has_rels = any([parents, children, in_calls, out_calls, tests, docs])
            graph_status = "connected" if has_rels else "isolated"
    
    # Truncate lists
    parents = parents[:max_neighbors]
    children = children[:max_neighbors]
    in_calls = in_calls[:max_neighbors]
    out_calls = out_calls[:max_neighbors]
    tests = tests[:max_neighbors]
    docs = docs[:max_neighbors]

    # 5. Enrichment
    enrichment = {}
    
    # Identify span_hash to fetch
    query_hash = None
    fallback_symbol = None
    
    if target_entity:
        query_hash = target_entity.span_hash
        # Extract short symbol name for fallback
        fallback_symbol = target_entity.id.split(":", 1)[-1]
        
    elif mode == "file" and file_entities:
        # Fallback: try to find a representative entity in this file
        stem = rel_path.stem.lower()
        for e in file_entities:
             # e.id is like "type:module.Class"
             if stem in e.id.lower():
                 query_hash = e.span_hash
                 fallback_symbol = e.id.split(":", 1)[-1]
                 break
        # 2. Fallback to first entity
        if not query_hash:
             query_hash = file_entities[0].span_hash
             fallback_symbol = file_entities[0].id.split(":", 1)[-1]

    db_path = index_path_for_read(repo_root)
    enrichment = _fetch_enrichment(
        db_path, 
        span_hash=query_hash,
        symbol=fallback_symbol,
        file_path=rel_path
    )

    # 6. Provenance
    provenance = _get_provenance(repo_root, rel_path)

    # 6. Provenance
    provenance = _get_provenance(repo_root, rel_path)

    return InspectionResult(
        path=str(rel_path),
        source_mode=mode,
        snippet=snippet,
        full_source=source_content if include_full_source else None,
        primary_span=primary_span,
        file_summary=enrichment.get("summary"), # Fallback logic could go here
        graph_status=graph_status,
        defined_symbols=defined_syms,
        parents=parents,
        children=children,
        incoming_calls=in_calls,
        outgoing_calls=out_calls,
        related_tests=tests,
        related_docs=docs,
        enrichment=enrichment,
        provenance=provenance
    )
