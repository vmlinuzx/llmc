"""
Configuration loader for docgen backends.
"""

import logging
from pathlib import Path
from typing import Any

from llmc.docgen.types import DocgenBackend

logger = logging.getLogger(__name__)


class DocgenConfigError(Exception):
    """Raised when docgen configuration is invalid."""
    pass


def load_docgen_backend(
    repo_root: Path,
    toml_data: dict[str, Any],
) -> DocgenBackend | None:
    """Load docgen backend from configuration.
    
    Args:
        repo_root: Absolute path to repository root
        toml_data: Parsed TOML configuration data
        
    Returns:
        DocgenBackend instance if enabled, None if disabled
        
    Raises:
        DocgenConfigError: If configuration is invalid
    """
    # Check if docgen section exists
    if "docs" not in toml_data:
        logger.debug("No [docs] section in config, docgen disabled")
        return None
    
    docs_config = toml_data["docs"]
    
    if "docgen" not in docs_config:
        logger.debug("No [docs.docgen] section in config, docgen disabled")
        return None
    
    docgen_config = docs_config["docgen"]
    
    # Check if enabled
    enabled = docgen_config.get("enabled", False)
    if not enabled:
        logger.info("Docgen is disabled in configuration")
        return None
    
    # Get backend type
    backend_type = docgen_config.get("backend")
    if not backend_type:
        raise DocgenConfigError(
            "Missing 'backend' field in [docs.docgen] configuration"
        )
    
    # Validate backend type
    valid_backends = {"shell", "llm", "http", "mcp"}
    if backend_type not in valid_backends:
        raise DocgenConfigError(
            f"Invalid backend type '{backend_type}'. "
            f"Must be one of: {', '.join(sorted(valid_backends))}"
        )
    
    # Dispatch to backend-specific loader
    if backend_type == "shell":
        from llmc.docgen.backends.shell import load_shell_backend
        return load_shell_backend(repo_root, docgen_config)
    elif backend_type == "llm":
        raise DocgenConfigError(
            "LLM backend not yet implemented. Use 'shell' backend for now."
        )
    elif backend_type == "http":
        raise DocgenConfigError(
            "HTTP backend not yet implemented. Use 'shell' backend for now."
        )
    elif backend_type == "mcp":
        raise DocgenConfigError(
            "MCP backend not yet implemented. Use 'shell' backend for now."
        )
    else:
        # Should never reach here due to validation above
        raise DocgenConfigError(f"Unknown backend type: {backend_type}")


def get_output_dir(toml_data: dict[str, Any]) -> str:
    """Get output directory from config.
    
    Args:
        toml_data: Parsed TOML configuration data
        
    Returns:
        Output directory path (relative to repo root)
    """
    default_output_dir = "DOCS/REPODOCS"
    
    if "docs" not in toml_data:
        return default_output_dir
    
    docs_config = toml_data["docs"]
    
    if "docgen" not in docs_config:
        return default_output_dir
    
    docgen_config = docs_config["docgen"]
    
    return docgen_config.get("output_dir", default_output_dir)


def get_require_rag_fresh(toml_data: dict[str, Any]) -> bool:
    """Get require_rag_fresh setting from config.
    
    Args:
        toml_data: Parsed TOML configuration data
        
    Returns:
        Whether to require RAG freshness (default: True)
    """
    default_require_rag_fresh = True
    
    if "docs" not in toml_data:
        return default_require_rag_fresh
    
    docs_config = toml_data["docs"]
    
    if "docgen" not in docs_config:
        return default_require_rag_fresh
    
    docgen_config = docs_config["docgen"]
    
    return docgen_config.get("require_rag_fresh", default_require_rag_fresh)
