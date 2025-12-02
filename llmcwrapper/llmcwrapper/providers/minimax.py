# llmcwrapper/providers/minimax.py
from __future__ import annotations

from typing import Any

# NOTE: API shapes for MiniMax vary by account/region/version.
# This driver is a scaffold; fill in base_url endpoints and auth headers in your config,
# or keep using placeholder behavior until ready.
from .base import ProviderDriver


class MiniMaxDriver(ProviderDriver):
    name = "minimax"

    def send(self, *, messages, tools, max_tokens, temperature, model, correlation_id, profile_cfg, resolved_cfg) -> dict[str, Any]:
        # Placeholder: echoes a minimal response to keep pipelines working.
        # TODO: implement real HTTP call using requests once your endpoint path is confirmed.
        text = "[minimax placeholder: implement HTTP call here]"
        return {
            "message": {"role": "assistant", "content": text},
            "usage": {"input_tokens": None, "output_tokens": None},
            "finish_reason": "stop"
        }
