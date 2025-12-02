# llmcwrapper/providers/anthropic.py
from __future__ import annotations

import os
import time
from typing import Any

import requests

from .base import ProviderDriver


class AnthropicDriver(ProviderDriver):
    name = "anthropic"

    def send(self, *, messages, tools, max_tokens, temperature, model, correlation_id, profile_cfg, resolved_cfg) -> dict[str, Any]:
        base_url = resolved_cfg["providers"]["anthropic"].get("base_url", "https://api.anthropic.com/v1/messages")
        api_key = os.environ.get(resolved_cfg["providers"]["anthropic"].get("env_key","ANTHROPIC_API_KEY"))
        version = resolved_cfg["providers"]["anthropic"].get("anthropic_version","2023-06-01")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": version,
            "content-type": "application/json",
            "client": "llmcwrapper",
            "client-request-id": correlation_id
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            # Anthropic tool schema differs; pass-through assumes already normalized at call site
            payload["tools"] = tools

        resp = requests.post(base_url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429:
            # naive backoff once
            time.sleep(1.0)
            resp = requests.post(base_url, headers=headers, json=payload, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"Anthropic error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        # Usage fields vary; normalize basic shape
        usage = {
            "input_tokens": data.get("usage",{}).get("input_tokens"),
            "output_tokens": data.get("usage",{}).get("output_tokens"),
        }
        content = ""
        if isinstance(data.get("content"), list) and data["content"]:
            # typical anthropic messages response
            parts = []
            for part in data["content"]:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text",""))
            content = "\n".join([p for p in parts if p])
        elif isinstance(data.get("content"), str):
            content = data["content"]
        else:
            content = "[anthropic: response content in unexpected format]"

        return {
            "message": {"role":"assistant", "content": content},
            "usage": usage,
            "finish_reason": data.get("stop_reason") or data.get("stop") or "stop"
        }
