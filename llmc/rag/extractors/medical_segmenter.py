"""
Hybrid Clinical Note Segmenter.
Splits text into sections based on headers and heuristics.
"""

import re

from .medical_headers import normalize_header

# Regex to detect potential headers (e.g., "History:", "PLAN", "1. History")
HEADER_PATTERN = re.compile(r"^(\d+\.\s*)?([A-Za-z\s\/]+):?$", re.MULTILINE)


class Segment:
    def __init__(self, section_type: str, content: str, start_line: int, end_line: int):
        self.section_type = section_type
        self.content = content
        self.start_line = start_line
        self.end_line = end_line

    def __repr__(self):
        return f"<Segment type={self.section_type} lines={self.start_line}-{self.end_line}>"


def segment_note(text: str) -> list[Segment]:
    """
    Segment a clinical note into typed sections.
    """
    lines = text.splitlines()
    segments: list[Segment] = []

    current_type = "unknown"
    current_content: list[str] = []
    current_start = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            current_content.append(line)
            continue

        # Check for header
        # 1. Exact match with colon
        if line_stripped.endswith(":"):
            candidate = line_stripped[:-1]
            norm_type = normalize_header(candidate)
            if norm_type:
                # Close previous segment
                if current_content:
                    segments.append(
                        Segment(
                            current_type,
                            "\n".join(current_content),
                            current_start,
                            i - 1,
                        )
                    )
                # Start new segment
                current_type = norm_type
                current_content = []
                current_start = i
                # Don't add the header line to content, or maybe add it?
                # Usually keep content clean.
                continue

        # 2. Uppercase check (e.g. ASSESSMENT)
        if line_stripped.isupper() and len(line_stripped) < 40:
            norm_type = normalize_header(line_stripped)
            if norm_type:
                if current_content:
                    segments.append(
                        Segment(
                            current_type,
                            "\n".join(current_content),
                            current_start,
                            i - 1,
                        )
                    )
                current_type = norm_type
                current_content = []
                current_start = i
                continue

        current_content.append(line)

    # Flush last segment
    if current_content:
        segments.append(
            Segment(
                current_type, "\n".join(current_content), current_start, len(lines) - 1
            )
        )

    return segments
