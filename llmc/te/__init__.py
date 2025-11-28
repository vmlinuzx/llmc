"""
LLMC Tool Envelope (TE) - Shell middleware for intelligent output handling.

TE intercepts standard shell commands and returns enriched, ranked,
progressively-disclosed output. It uses the response stream to signal
capabilities without input token cost.

Philosophy: LLMs are alien intelligences that already know Unix.
Don't teach through prompts. Teach through responses.
"""

from __future__ import annotations

__version__ = "0.1.0"
