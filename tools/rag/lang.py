from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

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


@lru_cache(maxsize=None)
def _language(name: str):
    try:
        return get_language(name)
    except Exception as exc:  # pragma: no cover - tree-sitter loader errors
        raise RuntimeError(f"Tree-sitter language '{name}' not available: {exc}")


@lru_cache(maxsize=None)
def _parser(name: str) -> Parser:
    parser = Parser()
    language = _language(name)
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:  # tree-sitter >=0.21 renamed setter to property assignment
        parser.language = language  # type: ignore[attr-defined]
    return parser


def language_for_path(path: Path) -> Optional[str]:
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
    doc_hint: Optional[str] = None,
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


def _python_doc_hint(node: Node, source: bytes) -> Optional[str]:
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
    return text.strip().strip('"\'')


def _collect_python(node: Node, source: bytes, file_path: Path, scope: Optional[List[str]] = None) -> List[SpanRecord]:
    scope = scope or []
    spans: List[SpanRecord] = []
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


def _collect_js(node: Node, source: bytes, file_path: Path, lang: str, scope: Optional[List[str]] = None) -> List[SpanRecord]:
    scope = scope or []
    spans: List[SpanRecord] = []
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


def _collect_go(node: Node, source: bytes, file_path: Path, scope: Optional[List[str]] = None) -> List[SpanRecord]:
    scope = scope or []
    spans: List[SpanRecord] = []

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


def _collect_java(node: Node, source: bytes, file_path: Path, scope: Optional[List[str]] = None) -> List[SpanRecord]:
    scope = scope or []
    spans: List[SpanRecord] = []

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


def _collect_markdown(file_path: Path, source: bytes) -> List[SpanRecord]:
    if not source:
        return []

    lines = source.splitlines(keepends=True)
    if not lines:
        return []

    offsets: List[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    offsets.append(len(source))

    headings: List[Dict[str, Any]] = []
    for idx, raw_line in enumerate(lines):
        text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        match = MARKDOWN_HEADING_RE.match(text)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        if not title:
            continue
        headings.append({"line_idx": idx, "level": level, "title": title})

    if not headings:
        return []

    slug_counts: Dict[str, int] = {}
    spans: List[SpanRecord] = []
    total_lines = len(lines)

    for idx, heading in enumerate(headings):
        line_idx = int(heading["line_idx"])
        level = int(heading["level"])
        title = str(heading["title"])

        start_line = line_idx + 1
        start_byte = offsets[line_idx]
        if idx + 1 < len(headings):
            next_line_idx = int(headings[idx + 1]["line_idx"])
            end_line = next_line_idx
            end_byte = offsets[next_line_idx]
        else:
            end_line = total_lines
            end_byte = offsets[-1]

        doc_hint = None
        for probe in range(line_idx + 1, end_line):
            candidate = lines[probe].decode("utf-8", errors="replace").strip()
            if candidate:
                doc_hint = candidate[:200]
                break

        slug = _slugify(title)
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
        if slug_counts[slug] > 1:
            slug = f"{slug}-{slug_counts[slug]}"

        spans.append(
            SpanRecord(
                file_path=file_path,
                lang="markdown",
                symbol=slug,
                kind=f"h{level}",
                start_line=start_line,
                end_line=end_line,
                byte_start=start_byte,
                byte_end=end_byte,
                span_hash="",
                doc_hint=doc_hint,
            )
        )

    return spans


LANG_EXTRACTORS: Dict[str, Callable[[Path, bytes], List[SpanRecord]]] = {
    "python": lambda path, src: _collect_python(parse_source("python", src), src, path),
    "javascript": lambda path, src: _collect_js(parse_source("javascript", src), src, path, "javascript"),
    "typescript": lambda path, src: _collect_js(parse_source("typescript", src), src, path, "typescript"),
    "tsx": lambda path, src: _collect_js(parse_source("tsx", src), src, path, "tsx"),
    "go": lambda path, src: _collect_go(parse_source("go", src), src, path),
    "java": lambda path, src: _collect_java(parse_source("java", src), src, path),
    "markdown": _collect_markdown,
}


def extract_spans(file_path: Path, lang: str, source: bytes) -> List[SpanRecord]:
    extractor = LANG_EXTRACTORS.get(lang)
    if extractor is None:
        return []
    spans = extractor(file_path, source)
    return spans
