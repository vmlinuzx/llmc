import os
import sys
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

pytest_plugins = [
    "tests._plugins.pytest_ruthless",
    "tests._plugins.pytest_compat_shims",
]


# Ensure repo root is importable as a package root (for `tools.*`).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def _session_env(tmp_path_factory: pytest.TempPathFactory) -> None:
    """
    Session-level hermetic env that does not depend on the function-scoped
    `monkeypatch` fixture (avoids ScopeMismatch).
    """
    home = tmp_path_factory.mktemp("home")
    mp = MonkeyPatch()
    mp.setenv("HOME", str(home))
    mp.setenv("PYTHONHASHSEED", "0")
    try:
        yield
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def hermetic_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Autouse: each test runs in its own tmp cwd, and XDG dirs stay inside tmp.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path

