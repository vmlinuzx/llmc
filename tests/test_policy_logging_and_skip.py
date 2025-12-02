from __future__ import annotations

import logging

from tools.rag_repo.logging import warn_skip


def test_warn_skip_emits_warning(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="llmc.paths")
    warn_skip("entryA", "bad workspace path")
    assert any("skip entryA: bad workspace path" in record.message for record in caplog.records)
