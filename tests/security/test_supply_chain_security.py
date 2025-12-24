"""
Test to verify supply chain security.
"""
import importlib
import os
import pytest

def is_rag_install() -> bool:
    """Check if this is a RAG-enabled installation."""
    # A simple proxy for this is checking if a known RAG-specific dependency is installed.
    # In the future, this could be a more robust check (e.g., an env var).
    try:
        importlib.import_module("tree_sitter")
        return True
    except ImportError:
        return False

@pytest.mark.skipif(is_rag_install(), reason="Skipping supply chain check for RAG installs")
def test_no_huggingface_deps_in_default_install():
    """
    Verify that sentence-transformers (which downloads from Hugging Face)
    is not installed in the default configuration.
    
    This is a supply chain security measure to avoid accidental downloads
    from external sources unless explicitly opted in via `pip install .[rag]`.
    """
    try:
        importlib.import_module("sentence_transformers")
        # If the import succeeds, it means the package is present, which is a failure
        # for default (non-RAG) installations.
        pytest.fail(
            "'sentence-transformers' package found in a non-RAG installation. "
            "This poses a supply chain risk and should only be installed with "
            "the '[rag]' extra."
        )
    except ImportError:
        # This is the expected outcome for a default (non-RAG) installation.
        # The package should not be importable.
        pass
    except Exception as e:
        # Any other exception should fail the test
        pytest.fail(f"An unexpected error occurred: {e}")
