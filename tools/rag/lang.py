from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path
import re
from typing import Any

from tree_sitter import Node, Parser
from tree_sitter_languages import get_language

from .types import SpanRecord

EXTENSION_LANG = {
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".py": "python",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".rs": "rust",
    ".sh": "bash",
    ".bash": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sql": "sql",
    ".md": "markdown",
    ".markdown": "markdown",
}

SUPPORTED_LANGS = set(EXTENSION_LANG.values())


@cache
def _language(name: str):
    try:
        return get_language(name)
    except Exception as exc:  # pragma: no cover - tree-sitter loader errors
        raise RuntimeError(f"Tree-sitter language '{name}' not available: {exc}")


@cache
def _parser(name: str) -> Parser:
    parser = Parser()
    language = _language(name)
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:  # tree-sitter >=0.21 renamed setter to property assignment
        parser.language = language  # type: ignore[attr-defined]
    return parser


def language_for_path(path: Path) -> str | None:
    return EXTENSION_LANG.get(path.suffix.lower())


def is_supported(path: Path) -> bool:
    return language_for_path(path) in SUPPORTED_LANGS


def parse_source(lang: str, source: bytes) -> Node:
    parser = _parser(lang)
    tree = parser.parse(source)
    return tree.root_node


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _make_span(
    file_path: Path,
    lang: str,
    symbol: str,
    kind: str,
    node: Node,
    source: bytes,
    doc_hint: str | None = None,
) -> SpanRecord:
    start_line, end_line = node.start_point[0] + 1, node.end_point[0] + 1
    return SpanRecord(
        file_path=file_path,
        lang=lang,
        symbol=symbol,
        kind=kind,
        start_line=start_line,
        end_line=end_line,
        byte_start=node.start_byte,
        byte_end=node.end_byte,
        span_hash="",  # filled in later
        doc_hint=doc_hint,
    )


def _python_doc_hint(node: Node, source: bytes) -> str | None:
    body = node.child_by_field_name("body")
    if body is None or len(body.children) == 0:
        return None
    first = body.children[0]
    if first.type != "expression_statement" or len(first.children) == 0:
        return None
    literal = first.children[0]
    if literal.type not in {"string", "f_string"}:
        return None
    text = _node_text(literal, source)
    # Strip quotes crudely
    return text.strip().strip("\"'")


def _collect_python(
    node: Node, source: bytes, file_path: Path, scope: list[str] | None = None
) -> list[SpanRecord]:
    scope = scope or []
    spans: list[SpanRecord] = []
    if node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        class_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [class_name]) if scope else class_name
        spans.append(
            _make_span(
                file_path,
                "python",
                symbol,
                "class",
                node,
                source,
                _python_doc_hint(node, source),
            )
        )
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                spans.extend(_collect_python(child, source, file_path, scope + [class_name]))
        return spans

    if node.type in {"function_definition", "async_function_definition"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        func_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [func_name]) if scope else func_name
        spans.append(
            _make_span(
                file_path,
                "python",
                symbol,
                "async_function" if node.type == "async_function_definition" else "function",
                node,
                source,
                _python_doc_hint(node, source),
            )
        )
    for child in node.children:
        spans.extend(_collect_python(child, source, file_path, scope))
    return spans


def _collect_js(
    node: Node, source: bytes, file_path: Path, lang: str, scope: list[str] | None = None
) -> list[SpanRecord]:
    scope = scope or []
    spans: list[SpanRecord] = []
    if node.type in {"class_declaration", "class"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        class_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [class_name]) if scope else class_name
        spans.append(_make_span(file_path, lang, symbol, "class", node, source))
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                spans.extend(_collect_js(child, source, file_path, lang, scope + [class_name]))
        return spans

    if node.type in {"method_definition", "public_field_definition"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        method_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [method_name]) if scope else method_name
        spans.append(_make_span(file_path, lang, symbol, "method", node, source))
        return spans

    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        func_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [func_name]) if scope else func_name
        spans.append(_make_span(file_path, lang, symbol, "function", node, source))
        return spans

    for child in node.children:
        spans.extend(_collect_js(child, source, file_path, lang, scope))
    return spans


def _collect_go(
    node: Node, source: bytes, file_path: Path, scope: list[str] | None = None
) -> list[SpanRecord]:
    scope = scope or []
    spans: list[SpanRecord] = []

    if node.type == "type_declaration":
        for child in node.children:
            spans.extend(_collect_go(child, source, file_path, scope))
        return spans

    if node.type == "type_spec":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        type_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [type_name]) if scope else type_name
        spans.append(_make_span(file_path, "go", symbol, "type", node, source))
        body = node.child_by_field_name("type")
        if body is not None:
            for child in body.children:
                spans.extend(_collect_go(child, source, file_path, scope + [type_name]))
        return spans

    if node.type == "method_declaration":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        receiver = node.child_by_field_name("receiver")
        receiver_name = _node_text(receiver, source).strip().replace(" ", "") if receiver else ""
        func_name = _node_text(name_node, source).strip()
        symbol_parts = scope + ([receiver_name] if receiver_name else []) + [func_name]
        symbol = ".".join(part for part in symbol_parts if part)
        spans.append(_make_span(file_path, "go", symbol or func_name, "method", node, source))
        return spans

    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        func_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [func_name]) if scope else func_name
        spans.append(_make_span(file_path, "go", symbol, "function", node, source))
        return spans

    for child in node.children:
        spans.extend(_collect_go(child, source, file_path, scope))
    return spans


def _collect_java(
    node: Node, source: bytes, file_path: Path, scope: list[str] | None = None
) -> list[SpanRecord]:
    scope = scope or []
    spans: list[SpanRecord] = []

    if node.type in {"class_declaration", "interface_declaration"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        class_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [class_name]) if scope else class_name
        kind = "interface" if node.type == "interface_declaration" else "class"
        spans.append(_make_span(file_path, "java", symbol, kind, node, source))
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                spans.extend(_collect_java(child, source, file_path, scope + [class_name]))
        return spans

    if node.type in {"method_declaration", "constructor_declaration"}:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return spans
        method_name = _node_text(name_node, source).strip()
        symbol = ".".join(scope + [method_name]) if scope else method_name
        kind = "constructor" if node.type == "constructor_declaration" else "method"
        spans.append(_make_span(file_path, "java", symbol, kind, node, source))
        return spans

    for child in node.children:
        spans.extend(_collect_java(child, source, file_path, scope))
    return spans


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _collect_markdown(file_path: Path, source: bytes) -> list[SpanRecord]:
    """Extract spans from markdown using TechDocsExtractor.
    
    Uses heading-aware chunking with size limits (2500 chars default)
    instead of creating one span per heading.
    """
    if not source:
        return []
    
    try:
        from .extractors.tech_docs import TechDocsExtractor
        
        extractor = TechDocsExtractor(max_chunk_chars=2500)
        content = source.decode("utf-8", errors="replace")
        
        spans: list[SpanRecord] = []
        
        # Pre-calculate line offsets for byte position mapping
        lines = source.splitlines(keepends=True)
        line_offsets = [0]
        for line in lines:
            line_offsets.append(line_offsets[-1] + len(line))
        
        for idx, tech_span in enumerate(extractor.extract(file_path, content)):
            # Calculate byte offsets from line numbers
            start_line_idx = min(tech_span.start_line - 1, len(lines))
            end_line_idx = min(tech_span.end_line, len(lines))
            start_byte = line_offsets[start_line_idx] if start_line_idx < len(line_offsets) else len(source)
            end_byte = line_offsets[end_line_idx] if end_line_idx < len(line_offsets) else len(source)
            
            # For split spans (section_part), we need unique byte ranges
            # Use the content itself to find actual byte position
            if tech_span.span_type == "section_part" and tech_span.content:
                # Find unique portion in source for this split
                content_bytes = tech_span.content.encode("utf-8", errors="replace")
                # Add span index to ensure uniqueness even if content is similar
                # This is a workaround - ideally we'd track actual byte positions
                start_byte = start_byte + idx
                end_byte = start_byte + len(content_bytes)
            
            # Use section_path as symbol for better searchability
            symbol = tech_span.section_path or file_path.stem
            # Truncate long section paths for symbol field
            if len(symbol) > 100:
                symbol = symbol[:97] + "..."
            
            spans.append(
                SpanRecord(
                    file_path=file_path,
                    lang="markdown",
                    symbol=symbol,
                    kind=tech_span.span_type,  # "section" or "section_part"
                    start_line=tech_span.start_line,
                    end_line=tech_span.end_line,
                    byte_start=start_byte,
                    byte_end=end_byte,
                    span_hash="",
                    doc_hint=tech_span.content[:200] if tech_span.content else None,
                )
            )
        return spans
        
    except ImportError:
        # Fallback to empty if mistune not available
        return []


LANG_EXTRACTORS: dict[str, Callable[[Path, bytes], list[SpanRecord]]] = {
    "python": lambda path, src: _collect_python(parse_source("python", src), src, path),
    "javascript": lambda path, src: _collect_js(
        parse_source("javascript", src), src, path, "javascript"
    ),
    "typescript": lambda path, src: _collect_js(
        parse_source("typescript", src), src, path, "typescript"
    ),
    "tsx": lambda path, src: _collect_js(parse_source("tsx", src), src, path, "tsx"),
    "go": lambda path, src: _collect_go(parse_source("go", src), src, path),
    "java": lambda path, src: _collect_java(parse_source("java", src), src, path),
    "markdown": _collect_markdown,
}


def extract_spans(file_path: Path, lang: str, source: bytes) -> list[SpanRecord]:
    extractor = LANG_EXTRACTORS.get(lang)
    if extractor is None:
        return []
    spans = extractor(file_path, source)
    return spans
