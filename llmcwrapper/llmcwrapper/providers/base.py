# llmcwrapper/providers/base.py
from __future__ import annotations

from typing import Any


class ProviderDriver:
    name: str = "base"
    def send(self, *, messages, tools, max_tokens, temperature, model, correlation_id, profile_cfg, resolved_cfg) -> dict[str, Any]:
        raise NotImplementedError
