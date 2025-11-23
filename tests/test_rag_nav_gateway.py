from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rag_nav.gateway import compute_route  # type: ignore  # noqa: E402
from tools.rag_nav.metadata import save_status  # type: ignore  # noqa: E402
from tools.rag_nav.models import IndexStatus  # type: ignore  # noqa: E402


def test_compute_route_no_status(tmp_path: Path) -> None:
    repo_root = tmp_path
    route = compute_route(repo_root)

    assert route.use_rag is False
    assert route.freshness_state == "UNKNOWN"
    assert route.status is None


def test_compute_route_stale_status(tmp_path: Path) -> None:
    repo_root = tmp_path
    status = IndexStatus(
        repo=str(repo_root),
        index_state="stale",
        last_indexed_at="2025-01-01T00:00:00Z",
        last_indexed_commit=None,
        schema_version="1",
        last_error=None,
    )
    save_status(repo_root, status)

    route = compute_route(repo_root)
    assert route.use_rag is False
    assert route.freshness_state == "STALE"
    assert route.status is not None
    assert route.status.index_state == "stale"


def test_compute_route_fresh_with_matching_head(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    status = IndexStatus(
        repo=str(repo_root),
        index_state="fresh",
        last_indexed_at="2025-01-01T00:00:00Z",
        last_indexed_commit="abc123",
        schema_version="1",
        last_error=None,
    )
    save_status(repo_root, status)

    from tools.rag_nav import gateway

    monkeypatch.setattr(gateway, "_detect_git_head", lambda _: "abc123")

    route = gateway.compute_route(repo_root)
    assert route.use_rag is True
    assert route.freshness_state == "FRESH"
    assert route.status is not None
    assert route.status.index_state == "fresh"


def test_compute_route_fresh_with_mismatched_head(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    status = IndexStatus(
        repo=str(repo_root),
        index_state="fresh",
        last_indexed_at="2025-01-01T00:00:00Z",
        last_indexed_commit="abc123",
        schema_version="1",
        last_error=None,
    )
    save_status(repo_root, status)

    from tools.rag_nav import gateway

    monkeypatch.setattr(gateway, "_detect_git_head", lambda _: "deadbeef")

    route = gateway.compute_route(repo_root)
    assert route.use_rag is False
    assert route.freshness_state == "STALE"
    assert route.status is not None
    assert route.status.index_state == "fresh"
