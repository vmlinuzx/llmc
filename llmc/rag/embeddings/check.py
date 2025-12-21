"""
Check embedding model availability, primarily for Ollama.
"""

import json
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.error import URLError

from llmc.core import load_config


@dataclass
class EmbeddingCheckResult:
    """Result of a single embedding model check."""

    model_name: str
    passed: bool
    message: str


def check_embedding_models(repo_path: Path) -> List[EmbeddingCheckResult]:
    """
    Check all configured Ollama embedding models for availability.

    Args:
        repo_path: The path to the repository root.

    Returns:
        A list of EmbeddingCheckResult objects.
    """
    config = load_config(repo_path)
    if not config:
        return [
            EmbeddingCheckResult(
                model_name="unknown",
                passed=False,
                message="Could not load llmc.toml",
            )
        ]

    profiles = config.get("embeddings", {}).get("profiles", {})
    models_by_host = defaultdict(set)

    for _, profile in profiles.items():
        if profile.get("provider") == "ollama":
            model_name = profile.get("model")
            if model_name:
                # Use the configured api_base or fall back to localhost
                api_base = profile.get("ollama", {}).get(
                    "api_base", "http://localhost:11434"
                )
                models_by_host[api_base].add(model_name)

    if not models_by_host:
        return [
            EmbeddingCheckResult(
                model_name="none",
                passed=True,
                message="No Ollama embedding models configured.",
            )
        ]

    results = []
    for host, models_to_check in models_by_host.items():
        url = f"{host.rstrip('/')}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status != 200:
                    for model in models_to_check:
                        results.append(
                            EmbeddingCheckResult(
                                model_name=model,
                                passed=False,
                                message=f"Warning: Received status {response.status} from {host}.",
                            )
                        )
                    continue  # Move to the next host

                data = json.loads(response.read().decode("utf-8"))
                available_models = {
                    model["name"] for model in data.get("models", [])
                }
                available_base_models = {
                    model["name"].split(":")[0] for model in data.get("models", [])
                }

                for model_name in models_to_check:
                    base_model_name = model_name.split(":")[0]
                    if (
                        model_name in available_models
                        or base_model_name in available_base_models
                    ):
                        results.append(
                            EmbeddingCheckResult(
                                model_name=model_name,
                                passed=True,
                                message=f"Embedding model '{model_name}' is available at {host}.",
                            )
                        )
                    else:
                        results.append(
                            EmbeddingCheckResult(
                                model_name=model_name,
                                passed=False,
                                message=f"Warning: Embedding model '{model_name}' not found in Ollama at {host}. Suggestion: `ollama pull {model_name}`",
                            )
                        )

        except URLError:
            for model in models_to_check:
                results.append(
                    EmbeddingCheckResult(
                        model_name=model,
                        passed=False,
                        message=f"Warning: Ollama is not running or not reachable at {host}.",
                    )
                )
        except Exception as e:
            for model in models_to_check:
                results.append(
                    EmbeddingCheckResult(
                        model_name=model,
                        passed=False,
                        message=f"An unexpected error occurred while checking {host}: {e}",
                    )
                )

    return results
