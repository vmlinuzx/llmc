from __future__ import annotations

from pathlib import Path

import pytest

from tools.rag_repo.policy import PathPolicyError, PathSafetyPolicy, enforce_policy


def test_denylist_blocks(tmp_path: Path) -> None:
    policy = PathSafetyPolicy(denylist_prefixes=(str(tmp_path),))
    with pytest.raises(PathPolicyError):
        enforce_policy(tmp_path / "nope", policy)


def test_enforce_allows_ok(tmp_path: Path) -> None:
    policy = PathSafetyPolicy()
    path = enforce_policy(tmp_path / "ok", policy)
    assert str(path).endswith("ok")
