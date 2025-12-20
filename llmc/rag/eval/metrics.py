from pathlib import Path
from typing import Any

CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".rs", ".go", ".c", ".cpp", ".h", ".hpp",
    ".java", ".scala", ".kt", ".swift", ".rb", ".php", ".sh", ".bash",
    ".yaml", ".yml", ".json", ".toml", ".xml", ".html", ".css", ".scss",
    ".sql", ".lua", ".pl", ".pm", ".r", ".m", ".fs", ".fsi", ".hs", ".ex",
    ".exs", ".erl", ".hrl", ".clj", ".cljs", ".lisp", ".scm", ".el",
    ".vim", ".zsh", ".fish", ".bat", ".cmd", ".ps1"
}

def is_code_file(path: str | Path) -> bool:
    """Check if the path has a code extension."""
    if isinstance(path, str):
        path = Path(path)
    return path.suffix.lower() in CODE_EXTENSIONS

def code_at_k(results: list[dict[str, Any]], k: int = 5) -> float:
    """
    Calculate the fraction of top-k results that are code files.
    """
    if not results:
        return 0.0
    
    top_k = results[:k]
    if not top_k:
        return 0.0
        
    code_count = 0
    for res in top_k:
        # Assuming 'slice_id' or 'path' or 'file_path' contains the path.
        # Based on search results seen in codebase, 'slice_id' is often the path
        # or it has a 'path' field. Let's try to extract path.
        # Looking at fusion.py, results have 'slice_id'. 
        # In many systems slice_id is path:line_start:line_end or just path.
        # Let's check 'path' field first, then fallback to 'slice_id'.
        
        path_str = res.get("path")
        if not path_str:
            # Fallback to slice_id, stripping possible line numbers if needed
            # slice_id might be "src/main.py" or "src/main.py:10:20"
            slice_id = res.get("slice_id", "")
            if ":" in slice_id:
                # Naive heuristic: if it looks like path:line, split.
                # But windows paths have C:\...
                # Let's assume relative paths in repo usually.
                parts = slice_id.split(":")
                # If first part looks like a file...
                # This is tricky. Let's assume 'path' is populated if possible.
                # If not, let's treat slice_id as path if it doesn't have colons 
                # or if splitting gives a valid extension.
                path_str = parts[0]
            else:
                path_str = slice_id
                
        if path_str and is_code_file(path_str):
            code_count += 1
            
    return code_count / len(top_k)

def mrr_code(results: list[dict[str, Any]]) -> float:
    """
    Calculate Mean Reciprocal Rank (MRR) for the first code file.
    Returns 1/rank of first code file (1-based), or 0.0 if none found.
    """
    for i, res in enumerate(results):
        path_str = res.get("path")
        if not path_str:
            slice_id = res.get("slice_id", "")
            if ":" in slice_id:
                path_str = slice_id.split(":")[0]
            else:
                path_str = slice_id
        
        if path_str and is_code_file(path_str):
            return 1.0 / (i + 1)
            
    return 0.0
