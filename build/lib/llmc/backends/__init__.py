"""Unified backend layer for LLM providers.

This package provides LiteLLM-based backends for both:
- llmc_agent (async chat/tool calling) via LiteLLMAgentBackend
- llmc/rag (sync enrichment) via LiteLLMEnrichmentAdapter

Usage:
    from llmc.backends import LiteLLMConfig, LiteLLMAgentBackend
    
    config = LiteLLMConfig(model="ollama_chat/qwen3-next-80b")
    backend = LiteLLMAgentBackend(config)

See HLD: DOCS/planning/HLD-litellm-migration-FINAL.md
"""

from llmc.backends.litellm_agent import LiteLLMAgentBackend
from llmc.backends.litellm_core import LiteLLMConfig, LiteLLMCore, to_litellm_model
from llmc.backends.litellm_enrichment import LiteLLMEnrichmentAdapter

__all__ = [
    "LiteLLMConfig",
    "LiteLLMCore",
    "LiteLLMAgentBackend",
    "LiteLLMEnrichmentAdapter",
    "to_litellm_model",
]
