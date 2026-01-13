"""
Docgen Engine - AST-based documentation generator.

Parses Python source code and generates Markdown documentation.
"""

import ast
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DocgenEngine:
    """
    AST-based documentation generator.
    """

    def generate(self, source_code: str, source_path: str = "") -> str:
        """
        Generate markdown documentation from Python source code.

        Args:
            source_code: Python source code
            source_path: Path to source file (for logging/context)

        Returns:
            Generated markdown content
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.warning(f"Failed to parse {source_path}: {e}")
            return f"*Error parsing source code:* {e}"

        md_lines = []

        # Module Docstring
        docstring = ast.get_docstring(tree)
        if docstring:
            md_lines.append(docstring.strip())
            md_lines.append("")

        # Top-level Definitions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                md_lines.extend(self._process_class(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                md_lines.extend(self._process_function(node))

        if not md_lines:
            md_lines.append("*No documentation found.*")

        return "\n".join(md_lines)

    def _process_class(self, node: ast.ClassDef) -> list[str]:
        """Process a class definition."""
        lines = []
        lines.append(f"### Class `{node.name}`")
        lines.append("")

        docstring = ast.get_docstring(node)
        if docstring:
            lines.append(docstring.strip())
            lines.append("")

        # Process methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.extend(self._process_function(item, context=node.name))

        return lines

    def _process_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        context: Optional[str] = None,
    ) -> list[str]:
        """Process a function definition."""
        lines = []
        prefix = f"{context}." if context else ""

        # Build signature using ast.unparse for accuracy (requires Python 3.9+)
        try:
            # Create a dummy function with same args to unparse just the arguments
            # Actually, ast.unparse can handle arguments node directly in recent python versions
            args_str = ast.unparse(node.args)
        except Exception:
             # Fallback for older python or complex cases
             args_str = "..."

        is_async = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        sig = f"{is_async}def {prefix}{node.name}({args_str})"

        lines.append(f"#### `{sig}`")
        lines.append("")

        docstring = ast.get_docstring(node)
        if docstring:
            lines.append(docstring.strip())
            lines.append("")

        return lines
