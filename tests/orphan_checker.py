
from pathlib import Path
import re
import sys


def find_orphan_docs(docs_dir: str):
    markdown_files = {str(p.resolve()) for p in Path(docs_dir).rglob("*.md")}
    linked_files = set()

    for file_path in markdown_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                # print(f"Could not read {file_path}: {e}", file=sys.stderr)
                continue

        # Simple regex to find markdown links: [text](link)
        links = re.findall(r"\[.*?\]\((.*?)\)", content)

        for link in links:
            # Ignore absolute URLs, anchors, and mailto links
            if link.startswith(("http", "#", "mailto:", "file:")) or link == "":
                continue

            # remove anchor
            link_path_without_anchor = link.split("#")[0]
            if not link_path_without_anchor: # only anchor
                continue
                
            # Resolve the link path
            resolved_link_path = (Path(file_path).parent / Path(link_path_without_anchor)).resolve()
            linked_files.add(str(resolved_link_path))

    orphan_files = markdown_files - linked_files
    
    # Exclude some common root files that might not be linked internally
    # but are entry points.
    exclude_list = [
        str(Path(docs_dir).joinpath("index.md").resolve()),
        str(Path(docs_dir).joinpath("README.md").resolve())
    ]
    
    orphan_files = [p for p in orphan_files if p not in exclude_list]


    return orphan_files

if __name__ == "__main__":
    if len(sys.argv) > 1:
        docs_dir = sys.argv[1]
    else:
        docs_dir = "DOCS"

    orphans = find_orphan_docs(docs_dir)

    if orphans:
        print("Orphan documents found:")
        for file in orphans:
            # make path relative to docs_dir for readability
            print(f"  - {Path(file).relative_to(Path(docs_dir).resolve())}")
        sys.exit(1)
    else:
        print("No orphan documents found.")
        sys.exit(0)
