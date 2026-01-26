import ast
from dataclasses import dataclass
from typing import Any


@dataclass
class CallbackSite:
    lineno: int
    col_offset: int
    target_name: str
    tool_name: str
    args: list[Any]
    kwargs: dict[str, Any]

class ToolCallVisitor(ast.NodeVisitor):
    def __init__(self, allowed_tools: set[str]):
        self.allowed_tools = allowed_tools
        self.sites: list[CallbackSite] = []
        self.errors: list[str] = []

    def visit_Assign(self, node: ast.Assign):
        is_tool = self._is_tool_call(node.value)

        # Validation: Exactly 1 target
        if len(node.targets) != 1:
            if is_tool:
                self.errors.append(f"Line {node.lineno}: Tool calls must be assigned to a single variable (e.g. 'x = tool()')")
                return
            self.generic_visit(node)
            return

        target = node.targets[0]
        if not isinstance(target, ast.Name):
            if is_tool:
                self.errors.append(f"Line {node.lineno}: Tool calls must be assigned to a simple variable name")
                return
            self.generic_visit(node)
            return

        if not isinstance(node.value, ast.Call):
            self.generic_visit(node)
            return

        call_node = node.value
        tool_name = ""
        if isinstance(call_node.func, ast.Name):
            tool_name = call_node.func.id
        
        if tool_name not in self.allowed_tools:
            self.generic_visit(node)
            return

        # It is a tool call to an allowed tool.
        # Verify args are literals.
        try:
            args = [ast.literal_eval(arg) for arg in call_node.args]
            kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call_node.keywords if kw.arg}
        except ValueError:
            self.errors.append(f"Line {node.lineno}: Tool call arguments must be literal constants")
            return

        self.sites.append(CallbackSite(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target_name=target.id,
            tool_name=tool_name,
            args=args,
            kwargs=kwargs
        ))
        
        # Do NOT visit children of a successfully intercepted call

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in self.allowed_tools:
            # If we see a tool call here, it wasn't intercepted by visit_Assign
            self.errors.append(f"Line {node.lineno}: Tool calls must be assigned to a variable (bare or nested calls not allowed)")
        
        self.generic_visit(node)
        
    def _is_tool_call(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id in self.allowed_tools
        return False

def extract_tool_calls(code: str, allowed: set[str]) -> tuple[list[CallbackSite], list[str]]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [], [f"SyntaxError: {e}"]
        
    visitor = ToolCallVisitor(allowed)
    visitor.visit(tree)
    # Sort sites by line number to match execution order
    visitor.sites.sort(key=lambda s: s.lineno)
    return visitor.sites, visitor.errors

class RewriteTransformer(ast.NodeTransformer):
    def __init__(self, sites: list[CallbackSite], injections: list[str]):
        self.sites_map = {site.lineno: (site, inj) for site, inj in zip(sites, injections, strict=False)}
    
    def visit_Assign(self, node: ast.Assign):
        if node.lineno in self.sites_map:
            site, injected_name = self.sites_map[node.lineno]
            # Rewrite LHS = Name(injected_name)
            new_node = ast.Assign(
                targets=node.targets,
                value=ast.Name(id=injected_name, ctx=ast.Load()),
                type_comment=node.type_comment
            )
            ast.copy_location(new_node, node)
            return new_node
        return node

def rewrite_ast(code: str, sites: list[CallbackSite], injections: list[str]) -> str:
    tree = ast.parse(code)
    transformer = RewriteTransformer(sites, injections)
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
