from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import mistune


@dataclass
class TechDocsSpan:
    content: str           # The actual text content
    section_path: str      # Hierarchical path (e.g., "Install > Step 1")
    span_type: str         # "section", "paragraph", etc.
    start_line: int
    end_line: int
    metadata: dict         # Includes anchor, doc_title, file_path, etc.

class TechDocsExtractor:
    """Extracts semantic spans from technical documentation."""
    
    def __init__(self):
        self.markdown = mistune.create_markdown(renderer=None)

    def _slugify(self, text: str) -> str:
        # Lowercase, replace spaces with dashes, remove non-alphanumeric (except dashes)
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    def _get_text_content(self, node: dict[str, Any]) -> str:
        """Extract text content from a node (for headings/paths)."""
        if 'children' in node:
            return "".join(self._get_text_content(child) for child in node['children'])
        if 'raw' in node:
            return node['raw']
        return ""

    def _render_node(self, node: dict[str, Any]) -> str:
        """Reconstruct Markdown from an AST node (simplified)."""
        type_ = node.get('type')
        
        if type_ == 'heading':
            level = node.get('attrs', {}).get('level', 1)
            # For heading content, we usually want the formatted text too, but simplified is often okay.
            # Let's try to preserve formatting in headings too.
            text = "".join(self._render_node(child) for child in node.get('children', []))
            return f"{ '#' * level} {text}\n\n"
        
        elif type_ == 'paragraph':
            text = "".join(self._render_node(child) for child in node.get('children', []))
            return f"{text}\n\n"
        
        elif type_ == 'block_code':
            info = node.get('attrs', {}).get('info', '')
            code = node.get('raw', '')
            # Ensure code ends with newline if not present, though raw usually has it?
            # block_code raw usually includes the content.
            # We need to wrap it.
            return f"```{info}\n{code}```\n\n"
        
        elif type_ == 'blank_line':
            return "\n"
        
        elif type_ == 'list':
            # Simplified list rendering
            items = []
            for child in node.get('children', []):
                items.append(self._render_node(child))
            return "".join(items) + "\n"
            
        elif type_ == 'list_item':
            # This is hard to render perfectly without context (ordered/unordered)
            # Assuming unordered for now or just rendering content
            # List items usually contain other blocks (paragraphs etc) or just text?
            # In mistune, list_item children are usually block elements like paragraph.
            # If we just render them, we get "Text\n\n".
            # We want "- Text\n".
            # This is tricky. Let's just prefix the first child?
            content = "".join(self._render_node(child) for child in node.get('children', []))
            # Indent content?
            return f"- {content}" 
            
        elif type_ == 'text':
            return node.get('raw', '')

        elif type_ == 'codespan':
            return f"`{node.get('raw', '')}`"
            
        elif type_ == 'emphasis':
            return f"*{self._get_text_content(node)}*"

        elif type_ == 'strong':
            return f"**{self._get_text_content(node)}**"
            
        elif type_ == 'link':
             text = "".join(self._render_node(child) for child in node.get('children', []))
             href = node.get('attrs', {}).get('url', '')
             return f"[{text}]({href})"

        # Fallback for other types
        if 'children' in node:
            return "".join(self._render_node(child) for child in node['children'])
        
        return node.get('raw', '')

    def extract(self, path: Path, content: str) -> Iterator[TechDocsSpan]:
        ast = self.markdown(content)
        
        # State
        # Hierarchy: list of (level, title)
        hierarchy: list[tuple[int, str]] = []
        
        # Current chunk buffer
        current_chunk_nodes: list[dict[str, Any]] = []
        
        # We need to track the "current" section path for the accumulating nodes.
        # But the nodes themselves might *be* the heading that changes the path.
        # Approach: 
        # A chunk belongs to the section defined by the *last* heading.
        # When we hit a NEW heading:
        # 1. If we have accumulated content, yield it as a chunk belonging to `current_hierarchy`.
        # 2. Update `current_hierarchy` based on the new heading.
        # 3. Start new accumulation (the new heading itself is part of the new chunk).
        
        # Initial section path (root)
        current_path_str = "" 
        
        # For approximate line tracking
        current_line = 1
        
        # Track used anchors for this document to ensure uniqueness
        used_slugs: set = set()
        
        for node in ast:
            node_type = node.get('type')
            
            if node_type == 'heading':
                # Yield previous chunk if it has content
                if current_chunk_nodes:
                     yield self._create_span(current_chunk_nodes, current_path_str, path, current_line, used_slugs)
                     # Update line count
                     chunk_text = "".join(self._render_node(n) for n in current_chunk_nodes)
                     current_line += chunk_text.count('\n')
                     current_chunk_nodes = []

                # Update hierarchy
                level = node.get('attrs', {}).get('level', 1)
                text = self._get_text_content(node)
                
                # Pop headers of same or lower rank (higher level number)
                while hierarchy and hierarchy[-1][0] >= level:
                    hierarchy.pop()
                
                hierarchy.append((level, text))
                
                # Build path string
                current_path_str = " > ".join(h[1] for h in hierarchy)
                
                # Add heading to new chunk
                current_chunk_nodes.append(node)
                
            else:
                # Add to current chunk
                current_chunk_nodes.append(node)
        
        # Yield final chunk
        if current_chunk_nodes:
            yield self._create_span(current_chunk_nodes, current_path_str, path, current_line, used_slugs)

    def _create_span(self, nodes: list[dict[str, Any]], section_path: str, file_path: Path, start_line: int, used_slugs: set) -> TechDocsSpan:
        # Render content
        content = "".join(self._render_node(node) for node in nodes).strip()
        
        # Calculate end line
        # This is relative to start_line.
        line_count = content.count('\n')
        end_line = start_line + line_count
        
        # Metadata
        # Anchor: file_path#slugified-heading
        # We need the heading of *this* chunk.
        # The heading should be the first node if it exists.
        anchor_heading = ""
        if nodes and nodes[0].get('type') == 'heading':
            anchor_heading = self._get_text_content(nodes[0])
        elif section_path:
            # Use the last part of section path if current chunk doesn't start with heading (e.g. continuation?)
            # But our logic ensures chunks start with heading or are "intro" (before first heading).
            # If intro, maybe no anchor or root?
            parts = section_path.split(" > ")
            anchor_heading = parts[-1] if parts else ""
        
        slug = self._slugify(anchor_heading)
        
        # Ensure uniqueness
        original_slug = slug
        counter = 1
        while slug in used_slugs:
            slug = f"{original_slug}-{counter}"
            counter += 1
        used_slugs.add(slug)
        
        anchor = f"{file_path}#{slug}" if slug else str(file_path)
        
        metadata = {
            'anchor': anchor,
            'section_path': section_path,
            'file_path': str(file_path),
            'doc_title': str(file_path.stem) # simplified
        }
        
        return TechDocsSpan(
            content=content,
            section_path=section_path,
            span_type="section",
            start_line=start_line,
            end_line=end_line,
            metadata=metadata
        )
