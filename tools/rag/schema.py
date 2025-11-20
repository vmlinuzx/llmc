"""
Schema Extraction Module for LLMC RAG

Extends existing tree-sitter parsing to extract entities (functions, classes, tables)
and relationships (calls, uses, reads, writes) for graph-based retrieval.

This builds on top of the existing lang.py infrastructure.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# tree_sitter import deferred to v2 - not needed for Python AST parsing
# from tree_sitter import Node

# Minimal language detection without tree-sitter dependency
def language_for_path(path: Path) -> Optional[str]:
    """Simple file extension-based language detection"""
    ext = path.suffix.lower()
    lang_map = {
        '.py': 'python',
        '.ts': 'typescript',
        '.js': 'javascript',
        '.java': 'java',
        '.go': 'go',
    }
    return lang_map.get(ext)


@dataclass
class Entity:
    """Represents a code entity (function, class, table, etc.)
    
    Phase 2 additions:
    - file_path: Stable path for matching with spans (without line numbers)
    - start_line: Start line number (for precise matching)
    - end_line: End line number (for precise matching)
    """
    id: str  # Unique identifier (e.g., "sym:auth.login")
    kind: str  # "function", "class", "table", "variable"
    path: str  # File path with line numbers (e.g., "src/auth.py:10-15")
    metadata: Dict = field(default_factory=dict)
    span_hash: Optional[str] = None # Phase 2: Link to enrichment record
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    
    def to_dict(self) -> dict:
        base = {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "metadata": self.metadata,
        }
        if self.span_hash:
            base["span_hash"] = self.span_hash
        if self.file_path:
            base["file_path"] = self.file_path
        if self.start_line is not None:
            base["start_line"] = self.start_line
        if self.end_line is not None:
            base["end_line"] = self.end_line
        return base


@dataclass
class Relation:
    """Represents a relationship between entities"""
    src: str  # Source entity ID
    edge: str  # Relationship type ("calls", "uses", "reads", "writes", "extends")
    dst: str  # Destination entity ID
    
    def to_dict(self) -> dict:
        return {
            "src": self.src,
            "edge": self.edge,
            "dst": self.dst,
        }


@dataclass
class SchemaGraph:
    """Complete entity-relation graph for a repository"""
    version: int = 1
    indexed_at: str = ""
    repo: str = ""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "indexed_at": self.indexed_at,
            "repo": self.repo,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
        }
    
    def save(self, path: Path):
        """Save graph to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SchemaGraph":
        """Reconstruct a SchemaGraph from a plain dict payload."""
        graph = cls(
            version=data.get("version", 1),
            indexed_at=data.get("indexed_at", ""),
            repo=data.get("repo", ""),
        )

        for e in data.get("entities", []):
            graph.entities.append(
                Entity(
                    id=e["id"],
                    kind=e["kind"],
                    path=e["path"],
                    metadata=e.get("metadata", {}),
                    span_hash=e.get("span_hash"), # Phase 2
                    file_path=e.get("file_path"),  # Phase 2
                    start_line=e.get("start_line"),  # Phase 2
                    end_line=e.get("end_line"),  # Phase 2
                )
            )

        for r in data.get("relations", []):
            graph.relations.append(
                Relation(
                    src=r["src"],
                    edge=r["edge"],
                    dst=r["dst"],
                )
            )

        return graph
    
    @classmethod
    def load(cls, path: Path) -> SchemaGraph:
        """Load graph from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
        
        graph = cls(
            version=data["version"],
            indexed_at=data["indexed_at"],
            repo=data["repo"],
        )
        
        graph.entities = [
            Entity(
                id=e["id"],
                kind=e["kind"],
                path=e["path"],
                metadata=e.get("metadata", {}),
                span_hash=e.get("span_hash"), # Phase 2
                file_path=e.get("file_path"),  # Phase 2
                start_line=e.get("start_line"),  # Phase 2
                end_line=e.get("end_line"),  # Phase 2
            )
            for e in data["entities"]
        ]
        
        graph.relations = [
            Relation(src=r["src"], edge=r["edge"], dst=r["dst"])
            for r in data["relations"]
        ]
        
        return graph


class PythonSchemaExtractor:
    """Extract entities and relations from Python code using AST"""
    
    def __init__(self, file_path: Path, source: str):
        self.file_path = file_path
        self.source = source
        self.module_name = file_path.stem
        self.entities: List[Entity] = []
        self.relations: List[Relation] = []
        self.current_scope: List[str] = [self.module_name]
        self.import_map: Dict[str, str] = {}
    
    def extract(self) -> Tuple[List[Entity], List[Relation]]:
        """Main extraction entry point"""
        try:
            tree = ast.parse(self.source)
            self.visit_module(tree)
        except SyntaxError as e:
            # Parser failed, skip this file gracefully
            print(f"Parse error in {self.file_path}: {e}")
            return [], []
        
        return self.entities, self.relations
    
    def _module_stem(self, module: Optional[str]) -> Optional[str]:
        if not module:
            return None
        return module.rsplit(".", 1)[-1]

    def _record_import(self, node: ast.Import) -> None:
        """Records 'import module [as alias]' statements."""
        for alias in node.names:
            module_name = alias.name  # e.g., "scripts.router"
            local_name = alias.asname or self._module_stem(module_name) or module_name # Use stem for local name if no alias
            
            stem = self._module_stem(module_name)
            if stem:
                self.import_map[local_name] = stem
            else:
                self.import_map[local_name] = module_name # Fallback if no stem (e.g. bare "import module")

    def _record_import_from(self, node: ast.ImportFrom) -> None:
        """Records 'from module import func [as alias]' statements."""
        if node.level > 0: # Ignore relative imports for now
            return

        base = node.module # e.g., "scripts.router"
        if not base: # This should not happen for level 0 imports
            return

        base_stem = self._module_stem(base)

        for alias in node.names:
            if alias.name == "*": # Ignore wildcard imports
                continue

            symbol = alias.name # e.g., "estimate_tokens_from_text"
            local_name = alias.asname or symbol

            if base_stem:
                target = f"{base_stem}.{symbol}" # e.g., "router.estimate_tokens_from_text"
            else:
                target = symbol # Fallback if no stem (e.g. from __future__ import annotations)
            
            self.import_map[local_name] = target

    def _resolve_callee_symbol(self, callee: str) -> str:
        """
        Return a fully qualified symbol name (without 'sym:' prefix)
        for the given callee, using import_map when possible.
        Fallback: treat callee as local to this module.
        """
        if "." in callee:
            # Handle cases like 'module.func()' or 'alias.func()'
            prefix, suffix = callee.split(".", 1)
            if prefix in self.import_map:
                resolved_prefix = self.import_map[prefix]
                return f"{resolved_prefix}.{suffix}"
        
        # Handle bare names 'func()' or 'alias()'
        if callee in self.import_map:
            return self.import_map[callee]
        
        # Fallback: treat callee as local to this module
        return f"{self.module_name}.{callee}"

    def visit_module(self, node: ast.Module):
        """Visit top-level module in two passes: first imports, then definitions."""
        # First pass: collect imports
        for item in node.body:
            if isinstance(item, ast.Import):
                self._record_import(item)
            elif isinstance(item, ast.ImportFrom):
                self._record_import_from(item)

        # Second pass: collect entities and relations
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self.visit_function(item)
            elif isinstance(item, ast.ClassDef):
                self.visit_class(item)
    
    def visit_function(self, node: ast.FunctionDef, class_name: Optional[str] = None):
        """Extract function entity and its relationships"""
        # Build qualified name
        if class_name:
            symbol = f"{class_name}.{node.name}"
        else:
            symbol = f"{self.module_name}.{node.name}"
        
        entity_id = f"sym:{symbol}"
        
        # Compute span hash
        # This must match the hash used by the enrichment pipeline (tools.rag.spans)
        # Hash input: "file_path:start_line:end_line" (relative to repo root conceptually)
        # Ideally we use the same utility, but for now we implement a stable hash here
        span_id = f"{self.file_path}:{node.lineno}:{node.end_lineno}"
        span_hash = hashlib.md5(span_id.encode()).hexdigest()[:16]

        # Create entity (Phase 2: include location fields)
        entity = Entity(
            id=entity_id,
            kind="function",
            path=f"{self.file_path}:{node.lineno}-{node.end_lineno}",
            metadata={
                "params": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None,
            },
            span_hash=span_hash,
            file_path=str(self.file_path),  # Phase 2: stable path for matching
            start_line=node.lineno,  # Phase 2
            end_line=node.end_lineno if node.end_lineno else node.lineno,  # Phase 2
        )
        self.entities.append(entity)
        
        # Extract call relationships
        self.current_scope.append(symbol)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                self.visit_call(child, entity_id)
        self.current_scope.pop()
    
    def visit_class(self, node: ast.ClassDef):
        """Extract class entity and its methods"""
        class_name = f"{self.module_name}.{node.name}"
        entity_id = f"type:{class_name}"
        
        span_id = f"{self.file_path}:{node.lineno}:{node.end_lineno}"
        span_hash = hashlib.md5(span_id.encode()).hexdigest()[:16]
        
        # Create class entity (Phase 2: include location fields)
        entity = Entity(
            id=entity_id,
            kind="class",
            path=f"{self.file_path}:{node.lineno}-{node.end_lineno}",
            metadata={
                "bases": [ast.unparse(base) for base in node.bases],
            },
            span_hash=span_hash,
            file_path=str(self.file_path),  # Phase 2
            start_line=node.lineno,  # Phase 2
            end_line=node.end_lineno if node.end_lineno else node.lineno,  # Phase 2
        )
        self.entities.append(entity)
        
        # Extract inheritance relationships
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_id = f"type:{self.module_name}.{base.id}"
                self.relations.append(
                    Relation(src=entity_id, edge="extends", dst=base_id)
                )
        
        # Visit methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self.visit_function(item, class_name)
    
    def visit_call(self, node: ast.Call, caller_id: str):
        """Extract function call relationship"""
        # Try to resolve the called function
        callee_name = None
        
        if isinstance(node.func, ast.Name):
            # Direct function call: foo()
            callee_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Method call: obj.method()
            if isinstance(node.func.value, ast.Name):
                callee_name = f"{node.func.value.id}.{node.func.attr}"
            else:
                callee_name = node.func.attr
        
        if callee_name:
            symbol = self._resolve_callee_symbol(callee_name)
            
            callee_id = f"sym:{symbol}"
            self.relations.append(
                Relation(src=caller_id, edge="calls", dst=callee_id)
            )


def extract_schema_from_file(file_path: Path) -> Tuple[List[Entity], List[Relation]]:
    """
    Extract entities and relations from a single file.
    
    Returns:
        Tuple of (entities, relations)
    """
    lang = language_for_path(file_path)
    
    if not lang:
        return [], []
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return [], []
    
    # Use Python AST parser for .py files
    if lang == "python":
        try:
            source_str = content.decode('utf-8')
            extractor = PythonSchemaExtractor(file_path, source_str)
            return extractor.extract()
        except UnicodeDecodeError:
            print(f"Failed to decode {file_path} as UTF-8")
            return [], []
    
    # Other languages not yet supported in v1
    return [], []


def build_schema_graph(repo_root: Path, file_paths: List[Path]) -> SchemaGraph:
    """
    Build complete schema graph from list of files.
    
    Args:
        repo_root: Root directory of repository
        file_paths: List of source files to analyze
    
    Returns:
        SchemaGraph with all entities and relations
    """
    from datetime import UTC, datetime
    
    graph = SchemaGraph(
        indexed_at=datetime.now(UTC).isoformat(),
        repo=str(repo_root),
    )
    
    all_entities = []
    all_relations = []
    
    for file_path in file_paths:
        entities, relations = extract_schema_from_file(file_path)
        all_entities.extend(entities)
        all_relations.extend(relations)
    
    # Deduplicate entities by ID
    seen_ids = set()
    for entity in all_entities:
        if entity.id not in seen_ids:
            graph.entities.append(entity)
            seen_ids.add(entity.id)
    
    # Deduplicate relations
    seen_relations = set()
    for relation in all_relations:
        key = (relation.src, relation.edge, relation.dst)
        if key not in seen_relations:
            graph.relations.append(relation)
            seen_relations.add(key)
    
    return graph



# ============================================================================
# Phase 2: Enriched Schema Graph Builder
# ============================================================================

def build_enriched_schema_graph(repo_root: Path, db_path: Path, file_paths: List[Path]) -> SchemaGraph:
    """Build schema graph with enrichment metadata merged from database.
    
    This is the Phase 2 integration function that:
    1. Builds the base schema graph from AST parsing
    2. Loads all enrichments from the database
    3. Matches entities to enrichments by (file_path, symbol) or location
    4. Attaches enrichment metadata to matching entities
    
    Args:
        repo_root: Root directory of repository
        db_path: Path to enrichment database (.rag/index_v2.db)
        file_paths: List of source files to analyze
    
    Returns:
        SchemaGraph with enrichment metadata attached to entities
    """
    from .database import Database
    
    # Step 1: Build base schema graph (entities + relations from AST)
    graph = build_schema_graph(repo_root, file_paths)
    
    # Step 2: Load enrichments from database
    db = Database(db_path)
    try:
        enrichments = db.fetch_all_enrichments()
        spans = db.fetch_all_spans()
    finally:
        db.close()
    
    # Step 3: Build mapping index for fast lookup.
    # Key: (normalized_file_path, symbol) -> EnrichmentRecord
    enrich_by_symbol: Dict[Tuple[str, str], any] = {}

    for enrich in enrichments:
        symbol = enrich.symbol
        # Try to find the corresponding span to get file path.
        for span in spans:
            if span.span_hash != enrich.span_hash:
                continue

            # Normalize path for matching (relative to repo_root).
            try:
                norm_path = str(Path(span.file_path).relative_to(repo_root))
            except ValueError:
                norm_path = str(span.file_path)

            # Primary key: (path, fully-qualified symbol) if available.
            key = (norm_path, symbol)
            enrich_by_symbol[key] = enrich

            # Fallback key: (path, short symbol) for legacy indices where
            # spans.symbol stored only the function name (e.g. "build_graph_for_repo")
            # instead of "module.build_graph_for_repo".
            short_symbol = symbol.split(".")[-1]
            if short_symbol != symbol:
                fallback_key = (norm_path, short_symbol)
                enrich_by_symbol.setdefault(fallback_key, enrich)
            break
    
    # Step 4: Match entities to enrichments and attach metadata
    enriched_count = 0
    unmatched_entities = []
    
    for entity in graph.entities:
        if not entity.file_path:
            continue  # Can't match without location
        
        # Normalize entity file path
        try:
            norm_entity_path = str(Path(entity.file_path).relative_to(repo_root))
        except ValueError:
            norm_entity_path = entity.file_path
        # Persist normalized path so JSON exports remain repo-relative.
        entity.file_path = norm_entity_path
        
        # Extract symbol from entity ID (strip "sym:" or "type:" prefix).
        symbol = entity.id
        if symbol.startswith("sym:"):
            symbol = symbol[4:]
        elif symbol.startswith("type:"):
            symbol = symbol[5:]
        
        # Try to find enrichment by (file_path, symbol).
        key = (norm_entity_path, symbol)
        enrich = enrich_by_symbol.get(key)

        # Legacy fallback: older indices may have stored only the short symbol
        # name in spans.symbol (e.g. "build_graph_for_repo"). If the fully-
        # qualified lookup failed, retry using the short name.
        if enrich is None:
            short_symbol = symbol.split(".")[-1]
            if short_symbol != symbol:
                fallback_key = (norm_entity_path, short_symbol)
                enrich = enrich_by_symbol.get(fallback_key)
        
        if enrich:
            # Attach enrichment fields to entity metadata
            _attach_enrichment_to_entity(entity, enrich)
            enriched_count += 1
        else:
            # Phase 2 policy: missing/partial enrichment is non-fatal.
            # We leave the entity.metadata untouched and record the
            # unmatched entity ID for logging/observability only.
            unmatched_entities.append(entity.id)
    
    # Step 5: Log integration stats
    total_entities = len(graph.entities)
    total_enrichments = len(enrichments)
    coverage_pct = (enriched_count / total_entities * 100) if total_entities > 0 else 0
    
    print(f"    📊 Enrichment integration: {enriched_count}/{total_entities} entities enriched ({coverage_pct:.1f}%)")
    print(f"    📊 Database had {total_enrichments} enrichments available")
    
    if unmatched_entities and len(unmatched_entities) <= 10:
        print(f"    ⚠️  Unmatched entities: {unmatched_entities[:10]}")
    elif unmatched_entities:
        print(f"    ⚠️  {len(unmatched_entities)} entities could not be matched to enrichments")
    
    return graph


def _attach_enrichment_to_entity(entity: Entity, enrich: any) -> None:
    """Internal helper to attach enrichment fields to entity metadata.
    
    Args:
        entity: Entity to enrich
        enrich: EnrichmentRecord with metadata
    """
    # Parse JSON fields if they're stored as strings
    import json
    
    def safe_json_load(value: Optional[str]) -> Optional[list]:
        if not value:
            return None
        try:
            return json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            return None
    
    # Attach all enrichment fields
    if enrich.summary:
        entity.metadata["summary"] = enrich.summary
    
    evidence = safe_json_load(enrich.evidence)
    if evidence:
        entity.metadata["evidence"] = evidence
    
    inputs = safe_json_load(enrich.inputs)
    if inputs:
        entity.metadata["inputs"] = inputs
    
    outputs = safe_json_load(enrich.outputs)
    if outputs:
        entity.metadata["outputs"] = outputs
    
    side_effects = safe_json_load(enrich.side_effects)
    if side_effects:
        entity.metadata["side_effects"] = side_effects
    
    pitfalls = safe_json_load(enrich.pitfalls)
    if pitfalls:
        entity.metadata["pitfalls"] = pitfalls
    
    if enrich.usage_snippet:
        entity.metadata["usage_snippet"] = enrich.usage_snippet
    
    if enrich.tags:
        entity.metadata["tags"] = enrich.tags
    
    # Always store symbol/span_hash for downstream tools.
    if getattr(enrich, "symbol", None):
        entity.metadata["symbol"] = enrich.symbol
    entity.metadata["span_hash"] = enrich.span_hash


def build_graph_for_repo(
    repo_root: Path,
    require_enrichment: bool = True,
    db_path: Optional[Path] = None,
) -> SchemaGraph:
    """Orchestration function to build a schema graph for a repository.

    This is the main entry point for Phase 2 that:

    1. Discovers source files in the repository.
    2. Builds either a plain AST-only graph (when require_enrichment=False)
       or an enriched graph backed by the SQLite index (when require_enrichment=True).
    3. Optionally validates that enrichment data is present and actually
       attached to entities in the graph.

    Args:
        repo_root:
            Root directory of the repository being indexed.
        require_enrichment:
            When True (default), the function will ensure that the enrichment
            database contains at least one enrichment row and that at least one
            entity in the resulting graph has enrichment metadata attached.
            When False, the function will build a plain AST-only graph and will
            not touch the database.
        db_path:
            Optional explicit path to the enrichment database. When omitted and
            require_enrichment is True, this defaults to ``repo_root/.rag/index_v2.db``.

    Returns:
        SchemaGraph: The built schema graph (plain or enriched depending on
        require_enrichment).

    Raises:
        RuntimeError:
            - If no source files are discovered under repo_root.
            - If require_enrichment is True but the database has zero rows in
              the ``enrichments`` table.
            - If require_enrichment is True and the database reports
              enrichments, but none of the entities in the graph ended up with
              enrichment metadata (indicating a mapping bug).
    """
    # Discover source files once; both plain and enriched modes share this.
    file_paths = _discover_source_files(repo_root)
    
    if not file_paths:
        raise RuntimeError(f"No source files found in {repo_root}")
    
    # Plain, AST-only graph path: never touches the DB.
    if not require_enrichment:
        return build_schema_graph(repo_root, file_paths)

    # Enriched path: wire DB + graph and validate coverage.
    if db_path is None:
        db_path = repo_root / ".rag" / "index_v2.db"

    graph = build_enriched_schema_graph(repo_root, db_path, file_paths)

    # Optionally validate enrichment presence and coverage.
    from .database import Database

    db = Database(db_path)
    try:
        enrich_count = db.conn.execute(
            "SELECT COUNT(*) FROM enrichments"
        ).fetchone()[0]
    finally:
        db.close()

    if enrich_count == 0:
        raise RuntimeError(
            "require_enrichment=True but database has 0 enrichments. "
            "Run enrichment pipeline first or set require_enrichment=False."
        )

    enriched_entities = sum(1 for e in graph.entities if "summary" in e.metadata)
    if enriched_entities == 0:
        raise RuntimeError(
            f"Enrichment integration failed: {enrich_count} enrichments in DB "
            "but 0 entities enriched in graph. Check ID mapping logic."
        )

    # P0: merge enrichment snippets from the DB into entity metadata in a fail-soft way.
    try:
        from .graph_enrich import enrich_graph_entities

        enrich_graph_entities(graph, repo_root)
    except Exception:
        # Graph enrichment is best-effort; never break graph building.
        pass

    return graph



def _discover_source_files(repo_root: Path, max_files: int = 10000) -> List[Path]:
    """Discover Python source files in a repository.

    This helper is intentionally conservative:

    * It walks ``repo_root`` recursively looking for ``*.py`` files.
    * It skips common virtualenv, cache, and VCS directories.
    * It returns **absolute** paths so that downstream extractors can always
      open the files regardless of the current working directory.
      Callers who need repo-relative paths can derive them via
      ``path.relative_to(repo_root)`` where appropriate.

    Args:
        repo_root:
            Root directory to search.
        max_files:
            Maximum number of files to return (safety limit).

    Returns:
        List[Path]: Absolute paths to discovered Python source files.
    """
    files: List[Path] = []
    exclude_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
    
    for path in repo_root.rglob("*.py"):
        # Skip excluded directories anywhere in the path.
        if any(part in exclude_dirs for part in path.parts):
            continue

        files.append(path)

        if len(files) >= max_files:
            break
    
    return files
