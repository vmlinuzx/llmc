"""
Functions for checking embedding provider connectivity and model availability.
"""

from pathlib import Path
from typing import Any, List

import requests

from llmc.core import load_config


class CheckResult:
    """Structured result for a single validation check."""

    def __init__(
        self, check_name: str, passed: bool, message: str, details: Any = None
    ):
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        """Convert result to a dictionary."""
        return {
            "check": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


def check_ollama_connectivity(api_base: str) -> bool:
    """Checks if an Ollama server is reachable at the given URL."""
    try:
        response = requests.get(api_base, timeout=5)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def get_available_ollama_models(api_base: str) -> List[str]:
    """Gets a list of available model names from an Ollama server."""
    try:
        response = requests.get(f"{api_base}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        return [model.get("name") for model in data.get("models", [])]
    except (requests.exceptions.RequestException, ValueError):
        return []


def check_embedding_models(repo_path: Path) -> List[CheckResult]:
    """
    Checks Ollama connectivity and embedding model availability based on llmc.toml.
    """
    results: list[CheckResult] = []
    try:
        config = load_config(repo_path)
        profiles = config.get("embeddings", {}).get("profiles", {})
    except Exception as e:
        results.append(
            CheckResult("config_load", False, f"Failed to load or parse llmc.toml: {e}")
        )
        return results

    if not profiles:
        results.append(
            CheckResult("embedding_config", True, "No embedding profiles found to check.")
        )
        return results

    checked_urls: set[str] = set()

    for profile_name, profile_config in profiles.items():
        if profile_config.get("provider") != "ollama":
            continue

        model_name = profile_config.get("model")
        ollama_config = profile_config.get("ollama", {})
        api_base = ollama_config.get("api_base", "http://localhost:11434")

        if not model_name:
            results.append(
                CheckResult(
                    "model_config",
                    False,
                    f"Profile '{profile_name}' is missing 'model' name.",
                    {"profile": profile_name},
                )
            )
            continue

        # Check connectivity for each unique URL only once
        if api_base not in checked_urls:
            is_connected = check_ollama_connectivity(api_base)
            if not is_connected:
                results.append(
                    CheckResult(
                        "ollama_connectivity",
                        False,
                        f"Ollama server is not reachable at {api_base}.",
                        {"url": api_base},
                    )
                )
                # If we can't connect, we can't check models for this URL
                checked_urls.add(api_base)
                # Continue to the next profile, which might use a different URL
                continue

            checked_urls.add(api_base)

        # If we reach here, we have a connection to the Ollama instance.
        # Check for the model.
        available_models = get_available_ollama_models(api_base)
        # A model name in the config (e.g., "nomic-embed-text") should match
        # a model in Ollama (e.g., "nomic-embed-text:latest").
        if not any(m.startswith(model_name) for m in available_models):
            results.append(
                CheckResult(
                    "model_availability",
                    False,
                    f"Embedding model '{model_name}' not found in Ollama at {api_base}.",
                    {
                        "profile": profile_name,
                        "model": model_name,
                        "url": api_base,
                        "available": available_models,
                    },
                )
            )
        else:
            results.append(
                CheckResult(
                    "model_availability",
                    True,
                    f"Embedding model '{model_name}' is available in Ollama.",
                    {"profile": profile_name, "model": model_name, "url": api_base},
                )
            )

    return results
