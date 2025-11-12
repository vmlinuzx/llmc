# llmcwrapper/providers/__init__.py
from .base import ProviderDriver
from .anthropic import AnthropicDriver
from .minimax import MiniMaxDriver

def get_provider_driver(name: str) -> ProviderDriver:
    name = (name or "").lower()
    if name == "anthropic":
        return AnthropicDriver()
    if name == "minimax":
        return MiniMaxDriver()
    raise ValueError(f"Unknown provider: {name}")
