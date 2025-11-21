"""
Compatibility shim for the llmcwrapper package layout.

The actual implementation lives under llmcwrapper/llmcwrapper/, but legacy
entry points expect `llmcwrapper.*` to resolve directly. This shim imports the
real package and mirrors its `__path__` so submodules such as
`llmcwrapper.cli.llmc_yolo` continue to work.
"""

from importlib import import_module
from typing import Any

_inner = import_module(".llmcwrapper", __name__)
__all__ = getattr(_inner, "__all__", [])

# Point this package's import search path at the real implementation so that
# imports like `llmcwrapper.cli` resolve to llmcwrapper/llmcwrapper/cli.
__path__ = _inner.__path__  # type: ignore[attr-defined]


def __getattr__(name: str) -> Any:
    """Delegate attribute lookups to the inner package."""
    return getattr(_inner, name)
