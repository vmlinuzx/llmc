#!/usr/bin/env python3
"""
AST-driven chunker built on tree-sitter spans.

The chunker emits semantically aligned chunks for Python, JavaScript/TypeScript,
Bash, and Markdown by walking the parsed syntax tree. Large nodes are recursively
split and every chunk includes parent/child metadata to aid retrieval healines.
Fallback chunking reuses the legacy character windowing when parsing is not
available or unrecognised file types are encountered.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
import logging

try:
    from tree_sitter import Node  # type: ignore
    from tree_sitter_languages import get_parser  # type: ignore
except ImportError:  # pragma: no cover - handled gracefully at runtime
    Node = None  # type: ignore
    get_parser = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    text: str
    metadata: dict[str, object | None]


class ASTChunker:
    """Generate AST-aligned chunks with graceful fallback."""

    LANGUAGE_BY_EXTENSION: dict[str, str] = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".cjs": "javascript",
        ".mjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".ksh": "bash",
        ".md": "markdown",
        ".markdown": "markdown",
        ".mdx": "markdown",
    }

    # Node types that often convey structure. Used both for top-level node
    # selection and recursive splitting candidates.
    STRUCTURAL_HINTS: dict[str, tuple[str, ...]] = {
        "python": (
            "module",
            "class_definition",
            "function_definition",
            "decorated_definition",
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
            "with_statement",
        ),
        "javascript": (
            "program",
            "class_declaration",
            "function_declaration",
            "method_definition",
            "lexical_declaration",
            "variable_declaration",
            "export_statement",
            "expression_statement",
        ),
        "typescript": (
            "program",
            "class_declaration",
            "function_declaration",
            "method_definition",
            "lexical_declaration",
            "variable_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "export_statement",
        ),
        "tsx": (
            "program",
            "class_declaration",
            "function_declaration",
            "method_definition",
            "lexical_declaration",
            "variable_declaration",
            "export_statement",
            "jsx_element",
        ),
        "bash": (
            "program",
            "function_definition",
            "if_statement",
            "while_statement",
            "for_statement",
            "case_statement",
        ),
        "markdown": (
            "document",
            "section",
            "paragraph",
            "atx_heading",
            "setext_heading",
            "fenced_code_block",
            "list",
            "list_item",
            "block_quote",
        ),
    }

    IGNORE_TYPES: tuple[str, ...] = (
        "comment",
        "block_comment",
        "line_comment",
        "ERROR",
    )

    def __init__(
        self,
        max_chars: int = 1000,
        overlap_chars: int = 200,
        header_chars: int = 240,
    ) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.header_chars = header_chars
        self._parsers: dict[str, object] = {}
        self._text: str = ""
        self._text_bytes: bytes = b""
        # Mapping from character index to byte offset in _text_bytes.
        self._char_to_byte_index: list[int] = []
        self._line_offsets: list[int] = []
        self._span_counter: int = 0

    # Public API ---------------------------------------------------------

    def chunk_text(self, text: str, file_path: str) -> list[tuple[str, dict]]:
        """
        Return chunk text + metadata pairs.
        """
        if not text.strip():
            return []

        language = self._detect_language(file_path)
        if not self._tree_sitter_available() or not language:
            return self._legacy_chunks(text, 0, len(text), "plain", None, "fallback")

        parser = self._get_parser(language)
        if parser is None:
            return self._legacy_chunks(text, 0, len(text), language, None, "fallback")

        try:
            self._reset_state(text)
            tree = parser.parse(self._text_bytes)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("tree-sitter parse failed for %s: %s", file_path, exc)
            return self._legacy_chunks(text, 0, len(text), language, None, "fallback")

        chunks = self._chunk_tree(tree.root_node, language)  # type: ignore[arg-type]

        if not chunks:
            return self._legacy_chunks(text, 0, len(text), language, None, "fallback")

        self._annotate_child_counts(chunks)
        return [(record.text, record.metadata) for record in chunks]

    # Core chunking ------------------------------------------------------

    def _chunk_tree(self, root: Node, language: str) -> list[ChunkRecord]:
        meaningful_children = self._meaningful_children(root)
        if not meaningful_children:
            meaningful_children = [root]

        self._span_counter = 0
        results: list[ChunkRecord] = []
        cursor_byte = root.start_byte

        for node in meaningful_children:
            if node.start_byte > cursor_byte:
                results.extend(
                    self._chunk_range(
                        cursor_byte,
                        node.start_byte,
                        language=language,
                        parent_node_type="interstitial",
                        parent_span=None,
                        role="interstitial",
                        depth=0,
                    )
                )
            results.extend(self._emit_node(node, language, parent_span=None, depth=0))
            cursor_byte = max(cursor_byte, node.end_byte)

        if cursor_byte < root.end_byte:
            results.extend(
                self._chunk_range(
                    cursor_byte,
                    root.end_byte,
                    language=language,
                    parent_node_type="trailing",
                    parent_span=None,
                    role="trailing",
                    depth=0,
                )
            )

        return results

    def _emit_node(
        self,
        node: Node,
        language: str,
        parent_span: str | None,
        depth: int,
    ) -> list[ChunkRecord]:
        if node.end_byte <= node.start_byte:
            return []
        node_text = self._slice(node.start_byte, node.end_byte)
        if not node.is_named or not node_text.strip():
            return []

        node_char_len = self._char_length(node.start_byte, node.end_byte)
        span_id = self._new_span_id(language, node.type)

        if node_char_len <= self.max_chars:
            metadata = self._build_metadata(
                span_id=span_id,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                node_type=node.type,
                language=language,
                role="node",
                parent_span=parent_span,
                depth=depth,
                ordinal=0,
                total_segments=1,
            )
            return [ChunkRecord(node_text, metadata)]

        # Oversize node → split
        header_end_char = min(
            self._byte_to_char(node.start_byte) + self.header_chars,
            self._byte_to_char(node.end_byte),
        )
        header_end_byte = self._char_to_byte(header_end_char)
        header_text = self._slice(node.start_byte, header_end_byte)

        records: list[ChunkRecord] = []
        if header_text.strip():
            header_meta = self._build_metadata(
                span_id=span_id,
                start_byte=node.start_byte,
                end_byte=header_end_byte,
                node_type=node.type,
                language=language,
                role="node_header",
                parent_span=parent_span,
                depth=depth,
                ordinal=0,
                total_segments=1,
            )
            records.append(ChunkRecord(header_text, header_meta))
        else:
            # Fallback: treat as regular chunk even though large.
            metadata = self._build_metadata(
                span_id=span_id,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                node_type=node.type,
                language=language,
                role="node",
                parent_span=parent_span,
                depth=depth,
                ordinal=0,
                total_segments=1,
            )
            return [ChunkRecord(node_text, metadata)]

        structural_children = self._structural_children(node, language, header_end_byte)
        cursor = header_end_byte

        for child in structural_children:
            if child.start_byte > cursor:
                records.extend(
                    self._chunk_range(
                        cursor,
                        child.start_byte,
                        language=language,
                        parent_node_type=node.type,
                        parent_span=span_id,
                        role="body_gap",
                        depth=depth + 1,
                    )
                )
            records.extend(self._emit_node(child, language, parent_span=span_id, depth=depth + 1))
            cursor = max(cursor, child.end_byte)

        if cursor < node.end_byte:
            records.extend(
                self._chunk_range(
                    cursor,
                    node.end_byte,
                    language=language,
                    parent_node_type=node.type,
                    parent_span=span_id,
                    role="body_remainder",
                    depth=depth + 1,
                )
            )

        return records

    def _chunk_range(
        self,
        start_byte: int,
        end_byte: int,
        *,
        language: str,
        parent_node_type: str,
        parent_span: str | None,
        role: str,
        depth: int,
    ) -> list[ChunkRecord]:
        start_char = self._byte_to_char(start_byte)
        end_char = self._byte_to_char(end_byte)
        if end_char <= start_char:
            return []

        segments: list[tuple[int, int]] = []
        cursor = start_char
        while cursor < end_char:
            approx_end = min(end_char, cursor + self.max_chars)
            chunk_text = self._text[cursor:approx_end]
            if not chunk_text.strip():
                cursor = approx_end if approx_end > cursor else cursor + 1
                continue

            if approx_end < end_char:
                rel_newline = chunk_text.rfind("\n")
                if rel_newline != -1 and rel_newline > int(len(chunk_text) * 0.6):
                    approx_end = cursor + rel_newline + 1
            if approx_end <= cursor:
                approx_end = cursor + min(self.max_chars, end_char - cursor)
            segments.append((cursor, approx_end))
            if approx_end >= end_char:
                break
            cursor = max(approx_end - self.overlap_chars, cursor + 1)

        records: list[ChunkRecord] = []
        total = len(segments) or 1
        for ordinal, (seg_start_char, seg_end_char) in enumerate(segments):
            seg_start_byte = self._char_to_byte(seg_start_char)
            seg_end_byte = self._char_to_byte(seg_end_char)
            seg_text = self._slice(seg_start_byte, seg_end_byte)
            if not seg_text.strip():
                continue
            span_id = self._new_span_id(language, f"{parent_node_type}_segment")
            metadata = self._build_metadata(
                span_id=span_id,
                start_byte=seg_start_byte,
                end_byte=seg_end_byte,
                node_type=parent_node_type,
                language=language,
                role=role,
                parent_span=parent_span,
                depth=depth,
                ordinal=ordinal,
                total_segments=total,
            )
            records.append(ChunkRecord(seg_text, metadata))

        return records

    # Metadata helpers ---------------------------------------------------

    def _build_metadata(
        self,
        *,
        span_id: str,
        start_byte: int,
        end_byte: int,
        node_type: str,
        language: str,
        role: str,
        parent_span: str | None,
        depth: int,
        ordinal: int,
        total_segments: int,
    ) -> dict[str, object | None]:
        start_char = self._byte_to_char(start_byte)
        end_char = self._byte_to_char(end_byte)
        start_line, start_col = self._char_to_line_col(start_char)
        end_line, end_col = self._char_to_line_col(end_char)

        return {
            "span_id": span_id,
            "span_parent_id": parent_span,
            "span_role": role,
            "span_depth": depth,
            "span_ordinal": ordinal,
            "span_total_segments": total_segments,
            "chunk_strategy": "ast",
            "language": language,
            "node_type": node_type,
            "start": start_char,
            "end": end_char,
            "start_byte": start_byte,
            "end_byte": end_byte,
            "start_line": start_line,
            "end_line": end_line,
            "start_col": start_col,
            "end_col": end_col,
        }

    def _annotate_child_counts(self, chunks: Sequence[ChunkRecord]) -> None:
        child_map: dict[str, int] = {}
        for record in chunks:
            parent = record.metadata.get("span_parent_id")
            if parent:
                child_map[parent] = child_map.get(parent, 0) + 1
        for record in chunks:
            span_id = record.metadata.get("span_id")
            record.metadata["span_child_count"] = child_map.get(span_id, 0)

    # Tree traversal helpers ---------------------------------------------

    def _meaningful_children(self, node: Node) -> list[Node]:
        return [
            child
            for child in node.children
            if child.is_named
            and child.type not in self.IGNORE_TYPES
            and child.end_byte > child.start_byte
        ]

    def _structural_children(
        self,
        node: Node,
        language: str,
        lower_byte_bound: int,
    ) -> list[Node]:
        hints = self.STRUCTURAL_HINTS.get(language, ())
        meaningful: list[Node] = []
        stack = [node]
        while stack:
            current = stack.pop()
            for child in current.children:
                if child.start_byte < lower_byte_bound:
                    stack.append(child)
                    continue
                if not child.is_named or child.type in self.IGNORE_TYPES:
                    continue
                if child.end_byte <= child.start_byte:
                    continue
                if child == node:
                    continue
                if child.type in hints:
                    meaningful.append(child)
                stack.append(child)
        meaningful = sorted(
            {child for child in meaningful if child != node},
            key=lambda c: c.start_byte,
        )
        return meaningful

    # Language + parser helpers ------------------------------------------

    def _detect_language(self, file_path: str) -> str | None:
        suffix = file_path.lower()
        for ext, lang in self.LANGUAGE_BY_EXTENSION.items():
            if suffix.endswith(ext):
                return lang
        return None

    def _tree_sitter_available(self) -> bool:
        return Node is not None and get_parser is not None

    def _get_parser(self, language: str):
        if language in self._parsers:
            return self._parsers[language]
        if not self._tree_sitter_available():
            return None
        try:
            parser = get_parser(language)
            self._parsers[language] = parser
            return parser
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("tree-sitter parser unavailable for %s: %s", language, exc)
            self._parsers[language] = None  # cache failure
            return None

    # Text/offset helpers ------------------------------------------------

    def _reset_state(self, text: str) -> None:
        self._text = text
        self._text_bytes = text.encode("utf-8", errors="ignore")
        self._char_to_byte_index = []

        byte_offset = 0
        for ch in text:
            self._char_to_byte_index.append(byte_offset)
            byte_offset += len(ch.encode("utf-8"))
        self._char_to_byte_index.append(byte_offset)

        self._line_offsets = [0]
        for idx, ch in enumerate(text):
            if ch == "\n":
                self._line_offsets.append(idx + 1)
        self._line_offsets.append(len(text) + 1)

    def _slice(self, start_byte: int, end_byte: int) -> str:
        return self._text_bytes[start_byte:end_byte].decode("utf-8", errors="ignore")

    def _char_length(self, start_byte: int, end_byte: int) -> int:
        return self._byte_to_char(end_byte) - self._byte_to_char(start_byte)

    def _char_to_byte(self, char_index: int) -> int:
        if char_index < 0:
            return 0
        if char_index >= len(self._char_to_byte_index):
            return self._char_to_byte_index[-1]
        return self._char_to_byte_index[char_index]

    def _byte_to_char(self, byte_offset: int) -> int:
        idx = bisect_right(self._char_to_byte_index, byte_offset) - 1
        return max(idx, 0)

    def _char_to_line_col(self, char_index: int) -> tuple[int, int]:
        if not self._line_offsets:
            return (1, 1)
        line_idx = bisect_right(self._line_offsets, char_index) - 1
        line_idx = max(line_idx, 0)
        line_start = self._line_offsets[line_idx]
        return (line_idx + 1, char_index - line_start + 1)

    def _new_span_id(self, language: str, node_type: str) -> str:
        span_id = f"{language}:{node_type}:{self._span_counter}"
        self._span_counter += 1
        return span_id

    # Legacy fallback ----------------------------------------------------

    def _legacy_chunks(
        self,
        text: str,
        start_char: int,
        end_char: int,
        language: str,
        parent_span: str | None,
        role: str,
    ) -> list[tuple[str, dict]]:
        if not text.strip():
            return []

        # Reuse the AST chunk metadata builder for consistency by
        # initialising mappings.
        self._reset_state(text)
        start_byte = self._char_to_byte(start_char)
        end_byte = self._char_to_byte(end_char)
        records = self._chunk_range(
            start_byte=start_byte,
            end_byte=end_byte,
            language=language,
            parent_node_type=role,
            parent_span=parent_span,
            role=role,
            depth=0,
        )
        for record in records:
            record.metadata["chunk_strategy"] = "fallback"
        self._annotate_child_counts(records)
        return [(record.text, record.metadata) for record in records]

    def fallback_chunks(self, text: str) -> list[tuple[str, dict]]:
        """Expose legacy chunking for external callers."""
        return self._legacy_chunks(
            text=text,
            start_char=0,
            end_char=len(text),
            language="plain",
            parent_span=None,
            role="fallback",
        )
