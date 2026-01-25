"""TreeSitterNav - Semantic code navigation using LLMC's existing infrastructure.

FIXES V1.1.0 ISSUE: Referenced non-existent llmc/chunking/ module.

Correct LLMC locations:
- Tree-sitter parsing: llmc/rag/lang.py (FUNCTIONAL, not OOP!)
- Skeletonization: llmc/rag/skeleton.py  
- Span records: llmc/rag/types.py (NOT schema.py!)
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# CORRECT IMPORTS - Using actual LLMC module locations
from llmc.rag.lang import (
    parse_source,
    language_for_path,
    EXTENSION_LANG,
)
from llmc.rag.skeleton import Skeletonizer
from llmc.rag.types import SpanRecord


@dataclass
class NavNode:
    """Represents a navigable code symbol."""
    name: str
    kind: str  # "class", "function", "method"
    start_line: int
    end_line: int
    signature: str
    docstring: str | None = None


@dataclass  
class SearchMatch:
    """Result from text/regex search."""
    text: str
    start_line: int
    end_line: int
    start_char: int
    end_char: int


class TreeSitterNav:
    """Semantic navigation SDK built on LLMC's existing RAG infrastructure."""
    
    def __init__(
        self,
        source: str | Path,
        language: str | None = None,
    ):
        if isinstance(source, Path):
            self.source_path = source
            self.source = source.read_text()
            language = language or language_for_path(source)
        else:
            self.source_path = None
            self.source = source
        
        self.language = language or "python"
        
        # Use LLMC's existing functional parser
        source_bytes = self.source.encode()
        self.tree = parse_source(self.language, source_bytes)
        
        # Use LLMC's existing skeletonizer for outline
        self._skeletonizer = Skeletonizer(source_bytes, self.language)
        
        # Build symbol index from tree-sitter spans
        self._symbols: dict[str, NavNode] = {}
        self._build_symbol_index(source_bytes)
        
        # Track chunks for read pagination
        self._chunk_cache: dict[str, list[str]] = {}
    
    def _build_symbol_index(self, source_bytes: bytes) -> None:
        """Build symbol index using tree-sitter traversal."""
        if self.language == "python":
            self._index_python_symbols(self.tree)
    
    def _index_python_symbols(self, root_node) -> None:
        """Extract Python symbols from tree-sitter AST."""
        def visit(node, prefix=""):
            # Process current node first
            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol_name = self.source[name_node.start_byte:name_node.end_byte]
                    full_name = f"{prefix}.{symbol_name}" if prefix else symbol_name
                    
                    body = node.child_by_field_name("body")
                    sig_end = body.start_byte if body else node.end_byte
                    signature = self.source[node.start_byte:sig_end].strip()
                    
                    self._symbols[full_name] = NavNode(
                        name=full_name,
                        kind="function" if node.type == "function_definition" else "async_function",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=signature[:200],
                        docstring=None,
                    )
            
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = self.source[name_node.start_byte:name_node.end_byte]
                    full_name = f"{prefix}.{class_name}" if prefix else class_name
                    
                    body = node.child_by_field_name("body")
                    sig_end = body.start_byte if body else node.end_byte
                    signature = self.source[node.start_byte:sig_end].strip()
                    
                    self._symbols[full_name] = NavNode(
                        name=full_name,
                        kind="class",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=signature[:200],
                        docstring=None,
                    )
                    
                    # Recurse into class body for methods
                    if body:
                        visit(body, prefix=full_name)
                        return  # Don't double-process
            
            # Recurse into all children
            for child in node.children:
                visit(child, prefix)
        
        visit(self.tree)
    
    def outline(self, max_depth: int = 3) -> str:
        """Get skeletal view using LLMC's Skeletonizer."""
        return self._skeletonizer.skeletonize()
    
    def ls(self, scope: str = "") -> list[str]:
        """List symbols, optionally filtered by scope prefix."""
        if not scope:
            return [
                node.signature 
                for name, node in self._symbols.items()
                if "." not in name
            ]
        
        prefix = scope + "."
        return [
            node.signature
            for name, node in self._symbols.items()
            if name.startswith(prefix) and name.count(".") == scope.count(".") + 1
        ]
    
    def read(self, symbol: str, chunk_index: int = 0, max_chars: int = 8000) -> str:
        """Read source code of a symbol with pagination."""
        node = self._symbols.get(symbol)
        if not node:
            available = list(self._symbols.keys())[:20]
            return f"Error: Symbol '{symbol}' not found. Available: {available}"
        
        lines = self.source.split('\n')
        full_code = '\n'.join(lines[node.start_line - 1:node.end_line])
        
        if len(full_code) <= max_chars:
            path = self.source_path or "<string>"
            return f"# {path}:{node.start_line}-{node.end_line}\n{full_code}"
        
        if symbol not in self._chunk_cache:
            self._chunk_cache[symbol] = self._split_into_chunks(full_code, max_chars)
        
        chunks = self._chunk_cache[symbol]
        
        if chunk_index >= len(chunks):
            return f"Error: chunk_index {chunk_index} out of range (0-{len(chunks)-1})"
        
        header = f"# {symbol} (chunk {chunk_index + 1}/{len(chunks)})\n"
        footer = ""
        if chunk_index < len(chunks) - 1:
            footer = f"\n# ... use read('{symbol}', {chunk_index + 1}) for next chunk"
        
        return header + chunks[chunk_index] + footer
    
    def _split_into_chunks(self, code: str, max_chars: int) -> list[str]:
        """Split code into chunks, preferring line boundaries."""
        chunks = []
        lines = code.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1
            if current_size + line_size > max_chars and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            current_chunk.append(line)
            current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def search(self, pattern: str, max_results: int = 20) -> list[SearchMatch]:
        """Search for regex pattern in source."""
        import re
        results = []
        
        try:
            for match in re.finditer(pattern, self.source):
                if len(results) >= max_results:
                    break
                
                start_line = self.source[:match.start()].count('\n') + 1
                end_line = self.source[:match.end()].count('\n') + 1
                
                results.append(SearchMatch(
                    text=match.group(0)[:200],
                    start_line=start_line,
                    end_line=end_line,
                    start_char=match.start(),
                    end_char=match.end(),
                ))
        except re.error as e:
            results.append(SearchMatch(
                text=f"Regex error: {e}",
                start_line=0,
                end_line=0,
                start_char=0,
                end_char=0,
            ))
        
        return results
    
    def get_info(self) -> dict[str, Any]:
        """Get metadata about loaded source."""
        return {
            "total_chars": len(self.source),
            "total_lines": self.source.count('\n') + 1,
            "estimated_tokens": len(self.source) // 4,
            "language": self.language,
            "symbol_count": len(self._symbols),
            "source_path": str(self.source_path) if self.source_path else None,
        }


def create_nav_tools(nav: TreeSitterNav) -> dict[str, callable]:
    """Create tool functions for sandbox injection."""
    return {
        "nav_outline": lambda: nav.outline(),
        "nav_ls": lambda scope="": nav.ls(scope),
        "nav_read": lambda symbol, chunk_index=0: nav.read(symbol, chunk_index),
        "nav_search": lambda pattern, max_results=20: [
            {"text": m.text, "line": m.start_line}
            for m in nav.search(pattern, max_results)
        ],
        "nav_info": lambda: nav.get_info(),
    }
