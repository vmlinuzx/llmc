from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import DEVNULL, PIPE, run
from typing import Optional

from tools.rag_nav.models import FreshnessState, IndexStatus

try:
    from tools.rag_nav.metadata import load_status
except ImportError:
    def load_status(*args, **kwargs):
        return None


@dataclass
class RouteDecision:
    """Routing decision for RAG Nav tools based on index freshness."""

    use_rag: bool
    freshness_state: FreshnessState
    status: Optional[IndexStatus]


def _detect_git_head(repo_root: Path) -> Optional[str]:
    """
    Return the current git HEAD SHA for the given repo, or None on error.
    """
    try:
        result = run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stdout=PIPE,
            stderr=DEVNULL,
            check=False,
            text=True,
        )
        sha = (result.stdout or "").strip()
        return sha or None
    except Exception:
        return None


def compute_route(repo_root: Path) -> RouteDecision:
    """
    Decide whether to use the RAG graph or a local fallback for a repo.

    Policy:
    - No status: UNKNOWN, do not use RAG.
    - index_state != 'fresh': STALE, do not use RAG.
    - fresh + missing HEAD or last_indexed_commit: UNKNOWN, do not use RAG.
    - fresh + matching HEAD: FRESH, use RAG.
    - fresh + mismatched HEAD: STALE, do not use RAG.
    """
    try:
        status = load_status(repo_root)
    except Exception:
        status = None

    if status is None:
        return RouteDecision(use_rag=False, freshness_state="UNKNOWN", status=None)

    index_state = getattr(status, "index_state", None)
    if (index_state or "").lower() != "fresh":
        return RouteDecision(use_rag=False, freshness_state="STALE", status=status)

    try:
        head = _detect_git_head(repo_root)
    except Exception:
        head = None
    
    last_indexed = getattr(status, "last_indexed_commit", None)

    if not head or not last_indexed:
        return RouteDecision(use_rag=False, freshness_state="UNKNOWN", status=status)

    if str(head) == str(last_indexed):
        return RouteDecision(use_rag=True, freshness_state="FRESH", status=status)

    return RouteDecision(use_rag=False, freshness_state="STALE", status=status)

