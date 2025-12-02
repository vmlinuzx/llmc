
from pathlib import Path

import pytest

from tests._utils.envelopes import assert_ok_envelope

pytestmark = pytest.mark.examples


def test_nav_search_happy_path(hermetic_env: Path):
    """Template nav test; replace with real tool calls when ready."""
    repo = hermetic_env / "repo"
    repo.mkdir()

    class Meta:
        status = "OK"
        source = "RAG_GRAPH"
        freshness_state = "FRESH"

    class Res:
        meta = Meta()
        items = [object()]
        source = "RAG_GRAPH"
        freshness_state = "FRESH"

    res = Res()
    assert_ok_envelope(res)

