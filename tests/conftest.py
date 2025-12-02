from collections.abc import Iterable
from pathlib import Path
import shutil
import sys

from _pytest.monkeypatch import MonkeyPatch
import pytest

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


@pytest.fixture(scope="session", autouse=True)
def _cleanup_repo_caches(request: pytest.FixtureRequest) -> None:
    """
    Session teardown hook: remove static analysis caches in the repo root.

    This keeps `.mypy_cache` (and similar) from growing unbounded when tests
    invoke tools like mypy against the real repository tree.
    """

    def _remove_paths(paths: Iterable[Path]) -> None:
        for path in paths:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.is_file():
                    path.unlink()
            except Exception:
                # Best-effort cleanup only; never fail the test run because of cache removal.
                continue

    def _finalizer() -> None:
        cache_paths = [
            ROOT / ".mypy_cache",
            ROOT / ".pytest_cache",
        ]
        _remove_paths(cache_paths)

    request.addfinalizer(_finalizer)


def pytest_collection_modifyitems(config, items):
    """Skip standalone test scripts that have their own main() function."""
    skip_standalone = pytest.mark.skip(reason="Standalone test script - run directly with python")
    skip_wrapper_scripts = pytest.mark.skip(
        reason="Personal wrapper scripts - not part of production code"
    )

    for item in items:
        # Skip files that have if __name__ == "__main__" in them
        # BUT only if they DON'T have pytest imports or fixtures
        if item.fspath and item.fspath.exists():
            content = item.fspath.read_text(encoding="utf-8")
            # Skip if it has main AND doesn't have pytest test markers
            if "if __name__ == \"__main__\":" in content:
                if "import pytest" not in content and "@pytest" not in content:
                    item.add_marker(skip_standalone)

            # Skip wrapper script tests (personal tools, not production)
            if "test_wrapper_scripts.py" in str(item.fspath):
                item.add_marker(skip_wrapper_scripts)
