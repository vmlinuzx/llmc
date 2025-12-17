import ast


class _SymbolFinder(ast.NodeVisitor):
    def __init__(self, target_line: int):
        self.target_line = target_line
        self.best_symbol: str | None = None
        self.scope_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_scoped_node(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._visit_scoped_node(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_scoped_node(node)

    def _visit_scoped_node(self, node):
        # Check if this node covers the target line
        # Note: node.end_lineno might be None on very old Python, but 3.12 is fine
        start = getattr(node, "lineno", -1)
        end = getattr(node, "end_lineno", -1)

        is_match = start <= self.target_line
        if end != -1:
            is_match = is_match and (self.target_line <= end)

        if is_match:
            # This node contains the line. It is a better match than its parent.
            # Record the current qualified name.
            current_name = ".".join(self.scope_stack + [node.name])
            self.best_symbol = current_name

        # Push scope and recurse to find potentially deeper matches
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()


def identify_symbol_at_line(source: str, line: int) -> str | None:
    """
    Returns the qualified symbol name (e.g., "MyClass.method") that encloses the given line.
    Returns None if the line is at module level or outside any function/class.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    finder = _SymbolFinder(line)
    finder.visit(tree)
    return finder.best_symbol
