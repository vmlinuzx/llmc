import threading
import time
from pathlib import Path

from watchfiles import Change

from llmc.rag.watcher import FileFilter, LLMCFilter, RepoWatcher, is_watchfiles_available


def test_watchfiles_available():
    assert is_watchfiles_available() is True


def test_llmc_filter_ignores_git(tmp_path):
    filter_ = LLMCFilter(FileFilter(tmp_path))
    assert filter_(Change.modified, str(tmp_path / ".git" / "config")) is False


def test_llmc_filter_allows_python(tmp_path):
    filter_ = LLMCFilter(FileFilter(tmp_path))
    assert filter_(Change.modified, str(tmp_path / "main.py")) is True


def test_watcher_detects_create(tmp_path):
    changes: list[Path] = []
    event = threading.Event()

    def on_change(path: Path) -> None:
        changes.append(path)
        event.set()

    watcher = RepoWatcher(tmp_path, on_change)
    watcher.start()

    target = tmp_path / "test.py"
    target.write_text("# new file")

    assert event.wait(timeout=2.0) is True
    watcher.stop()

    assert any(path.name == "test.py" for path in changes)


def test_watcher_stops_gracefully(tmp_path):
    watcher = RepoWatcher(tmp_path, lambda _: None)
    watcher.start()

    start = time.time()
    watcher.stop()
    elapsed = time.time() - start

    assert elapsed < 3.0
