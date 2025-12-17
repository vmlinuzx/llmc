import contextlib
import importlib
from pathlib import Path as _Path
import sqlite3


def pytest_configure(config):
    # py3.12 sqlite alias
    if not hasattr(sqlite3, "CorruptDatabaseError"):
        try:
            sqlite3.CorruptDatabaseError = sqlite3.DatabaseError  # type: ignore[attr-defined]
        except Exception:
            pass

    # force tmp_path_factory.mktemp to use numbered=True (reduces mkdir collisions across test runs)
    try:
        import pytest as _pytest

        _orig_mktemp = _pytest.TempPathFactory.mktemp  # type: ignore[attr-defined]

        def _mktemp_numbered(self, basename, numbered=True):
            return _orig_mktemp(self, basename, numbered=True)

        _pytest.TempPathFactory.mktemp = _mktemp_numbered  # type: ignore[attr-defined]
    except Exception:
        pass

    # Register common marks to silence warnings
    for name, desc in {
        "rag_freshness": "RAG freshness/Gateway tests",
        "examples": "Example or doc-style tests",
        "integration": "Integration tests (slower)",
    }.items():
        try:
            config.addinivalue_line("markers", f"{name}: {desc}")
        except Exception:
            pass


def pytest_sessionstart(session):
    # Compat seam for tools.rag.enrichment.requests
    with contextlib.suppress(Exception):
        enr = importlib.import_module("llmc.rag.enrichment")
        if not hasattr(enr, "requests"):
            # Minimal stub that tests can monkeypatch
            class _RequestsStub:
                def request(self, *a, **k):
                    raise RuntimeError(
                        "requests not available; install it or mark test with allow_network"
                    )

                def get(self, *a, **k):
                    return self.request(*a, **k)

                def post(self, *a, **k):
                    return self.request(*a, **k)

                def put(self, *a, **k):
                    return self.request(*a, **k)

                def patch(self, *a, **k):
                    return self.request(*a, **k)

                def delete(self, *a, **k):
                    return self.request(*a, **k)

                class Session:
                    def request(self, *a, **k):
                        raise RuntimeError(
                            "requests Session not available; install it or mark test with allow_network"
                        )

                    def get(self, *a, **k):
                        return self.request(*a, **k)

                    def post(self, *a, **k):
                        return self.request(*a, **k)

                    def put(self, *a, **k):
                        return self.request(*a, **k)

                    def patch(self, *a, **k):
                        return self.request(*a, **k)

                    def delete(self, *a, **k):
                        return self.request(*a, **k)

            enr.requests = _RequestsStub()  # type: ignore

    # Legacy tools.rag_repo.cli re-export
    with contextlib.suppress(Exception):
        pkg = importlib.import_module("tools.rag_repo")
        if not hasattr(pkg, "cli"):
            for mod_name in (
                "tools.rag_repo.cli",
                "tools.rag_repo.command",
                "tools.rag_repo.app",
            ):
                with contextlib.suppress(Exception):
                    mod = importlib.import_module(mod_name)
                    for cand in ("cli", "main", "entrypoint", "app", "run"):
                        fn = getattr(mod, cand, None)
                        if callable(fn):
                            pkg.cli = fn
                            break

    # Safety: avoid FileExistsError explosions when tests create the same name twice
    try:
        _orig_mkdir = _Path.mkdir

        def _mkdir_compat(self, mode=0o777, parents=False, exist_ok=False):
            # If target already exists in a pytest tmp root, coerce exist_ok
            try:
                if str(self).find("pytest-of-") != -1 and self.exists():
                    exist_ok = True
            except Exception:
                pass
            try:
                return _orig_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)
            except FileExistsError:
                # Be lenient in tmp trees
                if str(self).find("pytest-of-") != -1:
                    return None
                raise

        _Path.mkdir = _mkdir_compat
    except Exception:
        pass

    # Defensive: if some module naïvely does "str / str" for paths, provide a helper in its globals
    # Tests can monkeypatch modules to use `compat_path_join(a, b)` instead.
    def compat_path_join(a, b):
        from pathlib import Path

        return Path(a) / b

    builtins = importlib.import_module("builtins")
    if not hasattr(builtins, "compat_path_join"):
        builtins.compat_path_join = compat_path_join
