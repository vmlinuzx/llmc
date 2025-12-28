
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from tree_sitter_languages import get_language, get_parser

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("graph_builder")

def build_graph_from_source(file_path: Path) -> Dict[str, Any]:
    """
    Parses a Python file using tree-sitter and extracts a graph of:
    - Nodes: Classes, Functions
    - Edges: Inheritance, Function Calls (basic)
    """
    language = get_language("python")
    parser = get_parser("python")
    
    code = file_path.read_bytes()
    tree = parser.parse(code)
    root = tree.root_node
    
    nodes = []
    edges = []
    
    # Helper to decode bytes
    def text(node) -> str:
        return code[node.start_byte : node.end_byte].decode("utf-8")

    # 1. Extract Definitions (Nodes)
    # query_scm = """
    # (class_definition name: (identifier) @name) @class
    # (function_definition name: (identifier) @name) @function
    # """
    # query = language.query(query_scm)
    # captures = query.captures(root)
    
    # We'll traverse manually for a bit more control over nesting/paths
    
    def traverse(node, parent_path: str = ""):
        cursor = node.walk()
        
        # Identify current scope
        current_path = parent_path
        
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                node_name = text(name_node)
                current_path = f"{parent_path}:{node_name}" if parent_path else node_name
                
                # Check for base classes (Inheritance Edges)
                bases = node.child_by_field_name("superclasses")
                if bases:
                    for child in bases.children:
                        if child.type == "identifier" or child.type == "attribute":
                            base_name = text(child)
                            edges.append({
                                "source": current_path,
                                "target": base_name, # Note: This assumes simple naming for now
                                "type": "INHERITS_FROM"
                            })

                nodes.append({
                    "id": current_path,
                    "name": node_name,
                    "type": "class",
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                })
                
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                node_name = text(name_node)
                # Differentiate methods from functions
                kind = "method" if ":" in parent_path else "function"
                current_path = f"{parent_path}.{node_name}" if parent_path else node_name
                
                nodes.append({
                    "id": current_path,
                    "name": node_name,
                    "type": kind,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                })

        # Look for Calls (Edges)
        if node.type == "call":
             # Very naive call extraction
             func_node = node.child_by_field_name("function")
             if func_node and parent_path: # defined inside something
                 target_name = text(func_node)
                 # Clean up typical python calls like self.foo or module.foo
                 if "." in target_name:
                     target_name = target_name.split(".")[-1] # Simplistic
                 
                 edges.append({
                     "source": parent_path,
                     "target": target_name,
                     "type": "CALLS"
                 })

        if node.child_count > 0:
            for child in node.children:
                traverse(child, current_path)

    traverse(root)
    
    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    target_file = Path("llmc/rag/graph_db.py")
    if not target_file.exists():
        print(f"File not found: {target_file}")
    else:
        print(f"--- Parsing {target_file} with Tree-Sitter ---")
        graph = build_graph_from_source(target_file)
        
        print(f"\nFound {len(graph['nodes'])} Nodes:")
        for n in graph['nodes']:
            print(f"  [{n['type'].upper()}] {n['id']} (L{n['start_line']}-L{n['end_line']})")
            
        print(f"\nFound {len(graph['edges'])} Edges (Sample):")
        # Dedupe edges for cleaner output
        unique_edges = set()
        for e in graph['edges']:
            sig = f"{e['source']} --[{e['type']}]--> {e['target']}"
            if sig not in unique_edges:
                unique_edges.add(sig)
                # Only show interesting ones
                if e['type'] == "INHERITS_FROM" or "GraphDatabase" in e['source']: 
                    print(f"  {sig}")

