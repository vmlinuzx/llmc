# llmcwrapper/providers/minimax.py
from __future__ import annotations
import os, requests, time
from typing import Any, Dict
from .base import ProviderDriver

class MiniMaxDriver(ProviderDriver):
    name = "minimax"

    def send(self, *, messages, tools, max_tokens, temperature, model, correlation_id, profile_cfg, resolved_cfg) -> Dict[str, Any]:
        minimax_cfg = resolved_cfg["providers"]["minimax"]
        base_url = minimax_cfg.get("base_url", "https://api.minimax.chat")

        chat_path = minimax_cfg.get("chat_path", "/v1/text/chatcompletion")
        if not chat_path.startswith("/"):
            chat_path = "/" + chat_path

        endpoint = base_url.rstrip("/") + chat_path

        api_key = os.environ.get(minimax_cfg.get("env_key", "MINIMAX_API_KEY"))
        if not api_key:
            raise RuntimeError("MINIMAX_API_KEY not set")

        auth_header = minimax_cfg.get("auth_header", "Authorization")
        auth_scheme = minimax_cfg.get("auth_scheme", "Bearer")

        headers = {
            auth_header: f"{auth_scheme} {api_key}",
            "content-type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429:
            time.sleep(1.0)
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"MiniMax error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()

        content = ""
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
            elif "messages" in choice:
                msg_parts = []
                for msg in choice["messages"]:
                    if msg.get("role") == "assistant" and "content" in msg:
                        msg_parts.append(msg["content"])
                content = "\n".join(msg_parts) if msg_parts else ""
        elif "output_text" in data:
            content = data["output_text"]
        else:
            content = "[minimax: unexpected response]"

        usage = {}
        if "usage" in data:
            usage_data = data["usage"]
            usage["input_tokens"] = usage_data.get("prompt_tokens") or usage_data.get("input_tokens")
            usage["output_tokens"] = usage_data.get("completion_tokens") or usage_data.get("output_tokens")
        else:
            usage = {"input_tokens": None, "output_tokens": None}

        finish_reason = "stop"
        if "choices" in data and data["choices"]:
            finish_reason = data["choices"][0].get("finish_reason", "stop")

        return {
            "message": {"role": "assistant", "content": content},
            "usage": usage,
            "finish_reason": finish_reason
        }
