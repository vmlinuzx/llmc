# llmcwrapper/capabilities.py

CAPABILITIES = {
    "anthropic": {
        "tools": True,
        "stream": True,
        "json": True,
        "vision": False,
        "responses_api": False,  # using messages v1 by default
        "tool_choice": True,
    },
    "minimax": {
        "tools": False,  # TODO: verify; set True when implemented
        "stream": False,
        "json": True,
        "vision": False,
        "responses_api": False,
        "tool_choice": False,
    },
}
