import importlib
import sys
from unittest.mock import patch

import pytest


def test_watcher_import_no_watchfiles():
    """
    Verify llmc.rag.watcher imports correctly even if watchfiles is missing.
    This simulates the environment where watchfiles is not installed.
    """
    # Remove the cached module to force reimport
    modules_to_remove = [k for k in sys.modules if k.startswith("llmc.rag.watcher")]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    # Also remove llmc.rag if it has watcher cached
    if "llmc.rag" in sys.modules:
        del sys.modules["llmc.rag"]

    # Patch watchfiles to simulate it being missing
    with patch.dict(sys.modules, {"watchfiles": None}):
        try:
            # Force fresh import
            from llmc.rag import watcher
            importlib.reload(watcher)

            assert watcher.is_watchfiles_available() is False
            assert watcher.WATCHFILES_AVAILABLE is False
        except ImportError:
            pytest.fail("llmc.rag.watcher raised ImportError")
        except AttributeError as e:
            pytest.fail(f"llmc.rag.watcher raised AttributeError: {e}")
        finally:
            # Clean up: remove the broken module so subsequent tests get fresh import
            modules_to_remove = [k for k in sys.modules if k.startswith("llmc.rag.watcher")]
            for mod in modules_to_remove:
                if mod in sys.modules:
                    del sys.modules[mod]
