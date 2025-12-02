import contextlib
import random
import sys
import time

try:
    import socket
except Exception:
    socket = None


def pytest_addoption(parser):
    grp = parser.getgroup("ruthless")
    grp.addoption(
        "--allow-network",
        action="store_true",
        help="Allow network sockets in tests (default: blocked)",
    )
    grp.addoption(
        "--allow-sleep", action="store_true", help="Allow time.sleep in tests (default: blocked)"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "allow_network: permit network access for this test")
    config.addinivalue_line("markers", "allow_sleep: permit time.sleep in this test")
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "requires_git: test requires git installed")


class _NoNetSocket:
    def __init__(self, *a, **k):
        raise RuntimeError(
            "Network is blocked by pytest_ruthless. Use --allow-network or @pytest.mark.allow_network"
        )


def _block_requests():
    try:
        import requests
    except Exception:
        return None
    orig = requests.Session.request

    def _deny(self, *a, **k):
        raise RuntimeError(
            "HTTP is blocked by pytest_ruthless. Use --allow-network or @pytest.mark.allow_network"
        )

    requests.Session.request = _deny
    return ("requests.Session.request", orig)


@contextlib.contextmanager
def _patched_sleep():
    orig = time.sleep

    def _deny_sleep(secs):
        raise RuntimeError(
            "time.sleep blocked by pytest_ruthless. Use --allow-sleep or @pytest.mark.allow_sleep"
        )

    time.sleep = _deny_sleep
    try:
        yield
    finally:
        time.sleep = orig


def pytest_runtest_setup(item):
    # Seed randomness per test for determinism
    seed = 1337
    random.seed(seed)
    try:
        import numpy as np  # type: ignore

        np.random.seed(seed)  # type: ignore
    except Exception:
        pass


import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    allow_net = item.config.getoption("--allow-network") or bool(
        item.get_closest_marker("allow_network")
    )
    allow_sleep = item.config.getoption("--allow-sleep") or bool(
        item.get_closest_marker("allow_sleep")
    )

    # Network guard
    restores = []
    if not allow_net and socket is not None:
        restores.append(("socket.socket", socket.socket))
        socket.socket = _NoNetSocket  # type: ignore[attr-defined]
        # requests
        r = _block_requests()
        if r:
            restores.append(r)

    # Sleep guard
    cm = _patched_sleep() if not allow_sleep else contextlib.nullcontext()
    with cm:
        try:
            yield
        finally:
            for name, orig in restores:
                mod_name, attr = name.rsplit(".", 1)
                mod = sys.modules.get(mod_name)
                if mod is not None:
                    setattr(mod, attr, orig)
