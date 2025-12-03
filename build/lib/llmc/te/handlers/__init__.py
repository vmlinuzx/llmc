"""
TE command handlers.

Each handler wraps an underlying tool, applies workspace rules,
ranks results, and produces streaming breadcrumbs.
"""

from __future__ import annotations

from .grep import handle_grep

__all__ = ["handle_grep"]
