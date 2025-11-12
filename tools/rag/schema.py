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
    """Represents a code entity (function, class, table, etc.)"""
    id: str  # Unique identifier (e.g., "sym:auth.login")
    kind: str  # "function", "class", "table", "variable"
    path: str  # File path with line numbers (e.g., "src/auth.py:10-15")
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "metadata": self.metadata,
        }


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
    
    def visit_module(self, node: ast.Module):
        """Visit top-level module"""
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
        
        # Create entity
        entity = Entity(
            id=entity_id,
            kind="function",
            path=f"{self.file_path}:{node.lineno}-{node.end_lineno}",
            metadata={
                "params": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None,
            }
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
        
        # Create class entity
        entity = Entity(
            id=entity_id,
            kind="class",
            path=f"{self.file_path}:{node.lineno}-{node.end_lineno}",
            metadata={
                "bases": [ast.unparse(base) for base in node.bases],
            }
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
            callee_id = f"sym:{self.module_name}.{callee_name}"
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
            callee_id = f"sym:{self.module_name}.{callee_name}"
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
            callee_id = f"sym:{self.module_name}.{callee_name}"
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
    from datetime import datetime
    
    graph = SchemaGraph(
        indexed_at=datetime.utcnow().isoformat() + "Z",
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
