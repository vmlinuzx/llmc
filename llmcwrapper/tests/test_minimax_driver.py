# llmcwrapper/tests/test_minimax_driver.py
from __future__ import annotations
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, '/home/vmlinux/src/llmc')

from llmcwrapper.providers.minimax import MiniMaxDriver

class TestMiniMaxDriver(unittest.TestCase):
    def setUp(self):
        self.driver = MiniMaxDriver()
        self.resolved_cfg = {
            "providers": {
                "minimax": {
                    "base_url": "https://api.minimax.chat",
                    "env_key": "MINIMAX_API_KEY",
                    "chat_path": "/v1/text/chatcompletion"
                }
            }
        }

    @patch('llmcwrapper.providers.minimax.requests.post')
    def test_send_success(self, mock_post):
        os.environ["MINIMAX_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5
            }
        }
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        result = self.driver.send(
            messages=messages,
            tools=None,
            max_tokens=100,
            temperature=0.7,
            model="m2-lite",
            correlation_id="test-123",
            profile_cfg={},
            resolved_cfg=self.resolved_cfg
        )

        self.assertEqual(result["message"]["role"], "assistant")
        self.assertEqual(result["message"]["content"], "Hello!")
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertEqual(result["usage"]["output_tokens"], 5)
        self.assertEqual(result["finish_reason"], "stop")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["timeout"], 60)

        headers = call_args[1]["headers"]
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer test-key")

        endpoint = call_args[0][0]
        self.assertEqual(endpoint, "https://api.minimax.chat/v1/text/chatcompletion")

        del os.environ["MINIMAX_API_KEY"]

    @patch('llmcwrapper.providers.minimax.requests.post')
    @patch('llmcwrapper.providers.minimax.time.sleep')
    def test_retry_on_429(self, mock_sleep, mock_post):
        os.environ["MINIMAX_API_KEY"] = "test-key"

        first_response = MagicMock()
        first_response.ok = False
        first_response.status_code = 429
        first_response.text = "Rate limited"

        second_response = MagicMock()
        second_response.ok = True
        second_response.status_code = 200
        second_response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Success"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3}
        }

        mock_post.side_effect = [first_response, second_response]

        messages = [{"role": "user", "content": "Test"}]
        result = self.driver.send(
            messages=messages,
            tools=None,
            max_tokens=None,
            temperature=0.5,
            model="m2-lite",
            correlation_id="test-456",
            profile_cfg={},
            resolved_cfg=self.resolved_cfg
        )

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)
        self.assertEqual(result["message"]["content"], "Success")

        del os.environ["MINIMAX_API_KEY"]

    @patch('llmcwrapper.providers.minimax.requests.post')
    def test_error_on_non_ok(self, mock_post):
        os.environ["MINIMAX_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        with self.assertRaises(RuntimeError) as cm:
            self.driver.send(
                messages=messages,
                tools=None,
                max_tokens=100,
                temperature=0.7,
                model="m2-lite",
                correlation_id="test-789",
                profile_cfg={},
                resolved_cfg=self.resolved_cfg
            )

        self.assertIn("MiniMax error 400", str(cm.exception))

        del os.environ["MINIMAX_API_KEY"]

    @patch('llmcwrapper.providers.minimax.requests.post')
    def test_tools_ignored_gracefully(self, mock_post):
        os.environ["MINIMAX_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "No tools used"},
                "finish_reason": "stop"
            }]
        }
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        tools = [{"type": "some_tool", "description": "test"}]
        result = self.driver.send(
            messages=messages,
            tools=tools,
            max_tokens=100,
            temperature=0.7,
            model="m2-lite",
            correlation_id="test-999",
            profile_cfg={},
            resolved_cfg=self.resolved_cfg
        )

        call_args = mock_post.call_args
        self.assertIn("tools", call_args[1]["json"])

        del os.environ["MINIMAX_API_KEY"]

    @patch('llmcwrapper.providers.minimax.requests.post')
    def test_custom_auth_config(self, mock_post):
        os.environ["CUSTOM_API_KEY"] = "custom-key"

        resolved_cfg_custom = {
            "providers": {
                "minimax": {
                    "base_url": "https://api.minimax.chat",
                    "env_key": "CUSTOM_API_KEY",
                    "chat_path": "/v1/text/chatcompletion",
                    "auth_header": "X-API-KEY",
                    "auth_scheme": "Token"
                }
            }
        }

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop"
            }]
        }
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        result = self.driver.send(
            messages=messages,
            tools=None,
            max_tokens=None,
            temperature=0.7,
            model="m2-lite",
            correlation_id="test-custom",
            profile_cfg={},
            resolved_cfg=resolved_cfg_custom
        )

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        self.assertIn("X-API-KEY", headers)
        self.assertEqual(headers["X-API-KEY"], "Token custom-key")

        del os.environ["CUSTOM_API_KEY"]

if __name__ == "__main__":
    unittest.main()
