"""
Centralized model configuration for RAG enrichment.

This module provides a single source of truth for the default enrichment model,
eliminating hardcoded model names scattered across the codebase.

Precedence (highest to lowest):
1. ENRICH_MODEL environment variable
2. llmc.toml [enrichment].default_model
3. First enabled chain's model field
4. Fallback constant
"""

from __future__ import annotations

import os
from pathlib import Path

from llmc.core import find_repo_root, load_config

# Fallback constant - used only when no config is available
DEFAULT_ENRICHMENT_MODEL = "qwen3:4b-instruct"


def get_default_enrichment_model(repo_root: Path | None = None) -> str:
    """
    Get the default enrichment model from configuration.
    
    Resolution order:
    1. ENRICH_MODEL environment variable (if non-empty)
    2. llmc.toml [enrichment].default_model key
    3. First enabled [[enrichment.chain]] entry's model field
    4. Fallback constant: "qwen3:4b-instruct"
    
    Args:
        repo_root: Repository root path. If None, uses find_repo_root().
        
    Returns:
        Model name string (never empty).
    """
    # 1. Environment variable takes precedence
    env_model = os.getenv("ENRICH_MODEL", "").strip()
    if env_model:
        return env_model
    
    # 2-3. Try to load from config
    try:
        if repo_root is None:
            repo_root = find_repo_root()
        
        cfg = load_config(repo_root)
        enrichment = cfg.get("enrichment") or {}
        
        # 2. Check for explicit default_model key
        default_model = enrichment.get("default_model")
        if default_model and isinstance(default_model, str) and default_model.strip():
            return default_model.strip()
        
        # 3. Fall back to first enabled chain's model
        chain_entries = enrichment.get("chain") or []
        if isinstance(chain_entries, dict):
            # Single entry case (TOML quirk)
            chain_entries = [chain_entries]
        
        for entry in chain_entries:
            if not isinstance(entry, dict):
                continue
            # Skip disabled entries
            enabled = entry.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.lower() in ("true", "1", "yes", "on")
            if not enabled:
                continue
            # Get model if present and non-empty
            model = entry.get("model")
            if model and isinstance(model, str) and model.strip():
                return model.strip()
    
    except Exception:
        # Config loading failed - fall through to default
        pass
    
    # 4. Final fallback
    return DEFAULT_ENRICHMENT_MODEL
