"""
Skeletonization Module for LLMC RAG

Generates minimalist 'header-file' views of source code for efficient LLM context.
Removes implementation details while preserving architectural structure (signatures, docstrings, imports).
"""

from __future__ import annotations

from pathlib import Path
from tree_sitter import Node
from .lang import parse_source, _node_text


class Skeletonizer:
    def __init__(self, source: bytes, lang: str = "python"):
        self.source = source
        self.lang = lang
        self.root = parse_source(lang, source)
        self.lines: list[str] = []
        self._indent_unit = "    "  # Default, will detect if possible

    def skeletonize(self) -> str:
        if self.lang == "python":
            return self._skeletonize_python()
        # Fallback for others: return full source? or simple truncation?
        # For now, just return source to be safe, or implement JS later.
        return self.source.decode("utf-8", errors="replace")

    def _skeletonize_python(self) -> str:
        self.lines = []
        # We walk the top-level nodes of the file
        self._process_python_block(self.root, indent_level=0)
        return "\n".join(self.lines)

    def _process_python_block(self, node: Node, indent_level: int):
        # Iterate over children
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                child = cursor.node
                self._process_python_node(child, indent_level)
                if not cursor.goto_next_sibling():
                    break

    def _process_python_node(self, node: Node, indent_level: int):
        # Helper to add line with current indentation
        indent = " " * (indent_level * 4)  # Assuming 4 spaces for now

        if node.type in ("import_statement", "import_from_statement"):
            # Keep imports fully
            self.lines.append(self._get_text(node))

        elif node.type in ("function_definition", "async_function_definition"):
            self._handle_function(node, indent)

        elif node.type == "class_definition":
            self._handle_class(node, indent, indent_level)

        elif node.type == "decorated_definition":
            # Recurse to handle the decorated function/class
            # We want to print the decorator
            # Structure: decorated_definition -> (decorator*, definition)
            # We print decorators, then handle definition
            child_cursor = node.walk()
            if child_cursor.goto_first_child():
                while True:
                    child = child_cursor.node
                    if child.type == "decorator":
                        self.lines.append(indent + self._get_text(child))
                    else:
                        # The definition itself
                        if child.type in (
                            "function_definition",
                            "async_function_definition",
                        ):
                            self._handle_function(child, indent)
                        elif child.type == "class_definition":
                            self._handle_class(child, indent, indent_level)
                    if not child_cursor.goto_next_sibling():
                        break

        # For strict minimalism, we skip assignments, expressions, etc. at top level
        # unless they seem like constants (all caps?). Let's skip them for now.

    def _handle_function(self, node: Node, indent: str):
        # Extract signature
        # A function definition has: name, parameters, return_type (opt), body
        # We want everything *except* the body implementation.

        # Easy way: get text from start of node to start of body
        body = node.child_by_field_name("body")
        if not body:
            # abstract method or forward declaration?
            self.lines.append(indent + self._get_text(node))
            return

        # Get signature text
        # This includes 'def', name, params, return annotation, colon
        sig_text = (
            self.source[node.start_byte : body.start_byte]
            .decode("utf-8", errors="replace")
            .strip()
        )
        self.lines.append(indent + sig_text)

        # Handle Docstring
        docstring_node = self._get_docstring_node(body)
        if docstring_node:
            self.lines.append(indent + "    " + self._get_text(docstring_node))
            self.lines.append(indent + "    ...")
        else:
            self.lines.append(indent + "    ...")

        # Add a blank line for readability
        self.lines.append("")

    def _handle_class(self, node: Node, indent: str, indent_level: int):
        # Class definition: name, superclasses, body
        body = node.child_by_field_name("body")
        if not body:
            self.lines.append(indent + self._get_text(node))
            return

        # Signature
        sig_text = (
            self.source[node.start_byte : body.start_byte]
            .decode("utf-8", errors="replace")
            .strip()
        )
        self.lines.append(indent + sig_text)

        # Process Body
        # We need to manually iterate body children to handle docstrings and methods
        found_content = False

        # Check for docstring first
        docstring_node = self._get_docstring_node(body)
        if docstring_node:
            self.lines.append(indent + "    " + self._get_text(docstring_node))
            found_content = True

        # Walk body children
        cursor = body.walk()
        if cursor.goto_first_child():
            while True:
                child = cursor.node

                # Check for methods or nested classes
                if child.type in (
                    "function_definition",
                    "async_function_definition",
                    "decorated_definition",
                    "class_definition",
                ):
                    self._process_python_node(child, indent_level + 1)
                    found_content = True

                # Future: consider processing typed assignments.
                # For now, only methods/classes are included.

                if not cursor.goto_next_sibling():
                    break

        if not found_content:
            self.lines.append(indent + "    ...")

        self.lines.append("")

    def _get_docstring_node(self, body_node: Node) -> Node | None:
        # Python docstring is the first expression statement in body that is a string
        if body_node.child_count == 0:
            return None

        # Access children via list is not supported by tree-sitter-python properties directly usually,
        # but the Node object is iterable or has .children
        # The PyPI tree_sitter Binding uses .children list
        if not body_node.children:
            return None

        first = body_node.children[0]
        if first.type == "expression_statement":
            if not first.children:
                return None
            expr = first.children[0]
            if expr and expr.type == "string":
                return expr
        return None

    def _get_text(self, node: Node) -> str:
        return self.source[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )


def generate_repo_skeleton(repo_root: Path, max_files: int = 500) -> str:
    from .schema import _discover_source_files

    files = _discover_source_files(repo_root, max_files)
    output = []

    output.append(f"# Repo Skeleton for: {repo_root.name}")
    output.append("# Generated by LLMC RAG Skeletonizer")
    output.append(f"# File Count: {len(files)}\n")

    for file_path in sorted(files):
        try:
            rel_path = file_path.relative_to(repo_root)
            lang = "python" if file_path.suffix == ".py" else "text"

            if lang != "python":
                continue  # Skip non-python for now to reduce noise

            source = file_path.read_bytes()
            skel = Skeletonizer(source, lang).skeletonize()

            if not skel.strip():
                continue

            output.append(f"## File: {rel_path}")
            output.append(f"```{lang}")
            output.append(skel)
            output.append("```\n")

        except Exception as e:
            output.append(f"# Error processing {file_path.name}: {e}\n")

    return "\n".join(output)
