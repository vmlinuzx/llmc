from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

RAG_DIR_NAME = ".rag"
DEFAULT_INDEX_NEW = "index_v2.db"
DEFAULT_INDEX_OLD = "index.db"
DEFAULT_SPANS_NAME = "spans.jsonl"

MODEL_PRESETS = {
    # Preferred embedding profile: intfloat/e5-base-v2 with instruct-style prefixes.
    "intfloat/e5-base-v2": {
        "model": "intfloat/e5-base-v2",
        "dim": 768,
        "passage_prefix": "passage: ",
        "query_prefix": "query: ",
        "normalize": True,
    },
    # Legacy MiniLM encoder retained for feature-flag toggles and regression checks.
    "sentence-transformers/all-minilm-l6-v2": {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "passage_prefix": "",
        "query_prefix": "",
        "normalize": True,
    },
}

PRESET_ALIASES = {
    "e5": "intfloat/e5-base-v2",
    "e5-base": "intfloat/e5-base-v2",
    "e5-base-v2": "intfloat/e5-base-v2",
    "default": "intfloat/e5-base-v2",
    "minilm": "sentence-transformers/all-minilm-l6-v2",
    "all-minilm-l6-v2": "sentence-transformers/all-minilm-l6-v2",
}

DEFAULT_MODEL_PRESET = "intfloat/e5-base-v2"

DEFAULT_MODEL = MODEL_PRESETS[DEFAULT_MODEL_PRESET]["model"]
DEFAULT_MODEL_DIM = MODEL_PRESETS[DEFAULT_MODEL_PRESET]["dim"]
DEFAULT_PASSAGE_PREFIX = MODEL_PRESETS[DEFAULT_MODEL_PRESET]["passage_prefix"]
DEFAULT_QUERY_PREFIX = MODEL_PRESETS[DEFAULT_MODEL_PRESET]["query_prefix"]
DEFAULT_DEVICE_PREF = "auto"
DEFAULT_GPU_WAIT = True
DEFAULT_GPU_MIN_FREE_MB = 1536  # ~1.5 GiB
DEFAULT_GPU_MAX_RETRIES = 10
DEFAULT_GPU_RETRY_SECONDS = 30


def _to_path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def rag_dir(repo_root: Path) -> Path:
    """Return the repository-local directory that houses RAG artefacts."""
    return repo_root / RAG_DIR_NAME


def _env_index_path(repo_root: Path) -> Optional[Path]:
    explicit = os.getenv("LLMC_RAG_INDEX_PATH") or os.getenv("EMBEDDING_INDEX_PATH")
    if explicit:
        return _to_path(repo_root, explicit)

    name = os.getenv("EMBEDDING_INDEX_NAME")
    if name:
        return rag_dir(repo_root) / name

    return None


def index_path_for_write(repo_root: Path) -> Path:
    """Resolve the index database path that should be written to."""
    env_path = _env_index_path(repo_root)
    if env_path is not None:
        return env_path
    return rag_dir(repo_root) / DEFAULT_INDEX_NEW


def index_path_for_read(repo_root: Path) -> Path:
    """Resolve the index database path to read from, falling back to v1 if needed."""
    env_path = _env_index_path(repo_root)
    if env_path is not None:
        return env_path

    candidate_new = rag_dir(repo_root) / DEFAULT_INDEX_NEW
    if candidate_new.exists():
        return candidate_new

    return rag_dir(repo_root) / DEFAULT_INDEX_OLD


def spans_export_path(repo_root: Path) -> Path:
    """Return the JSONL export path, keyed by the active index version."""
    env_path = os.getenv("LLMC_RAG_SPANS_PATH")
    if env_path:
        return _to_path(repo_root, env_path)

    base_index = index_path_for_write(repo_root).name
    if base_index == DEFAULT_INDEX_OLD:
        filename = DEFAULT_SPANS_NAME
    else:
        stem = Path(base_index).stem
        filename = f"{stem}_spans.jsonl"
    return rag_dir(repo_root) / filename


def ensure_rag_storage(repo_root: Path) -> None:
    """Create the `.rag` directory if it does not exist."""
    rag_dir(repo_root).mkdir(parents=True, exist_ok=True)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _preset_defaults() -> dict:
    preset_env = os.getenv("EMBEDDINGS_MODEL_PRESET")
    if preset_env:
        key = preset_env.strip().lower()
        key = PRESET_ALIASES.get(key, key)
        preset = MODEL_PRESETS.get(key)
        if preset:
            return preset
    return MODEL_PRESETS[DEFAULT_MODEL_PRESET]


def embedding_model_preset() -> str:
    preset_env = os.getenv("EMBEDDINGS_MODEL_PRESET")
    if not preset_env:
        return DEFAULT_MODEL_PRESET
    key = preset_env.strip().lower()
    key = PRESET_ALIASES.get(key, key)
    if key in MODEL_PRESETS:
        return key
    return DEFAULT_MODEL_PRESET


def embedding_model_name() -> str:
    return os.getenv("EMBEDDINGS_MODEL_NAME", _preset_defaults()["model"])


def embedding_model_dim() -> int:
    raw = os.getenv("EMBEDDINGS_MODEL_DIM")
    if raw is not None:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return _preset_defaults()["dim"]


def embedding_passage_prefix() -> str:
    return os.getenv("EMBEDDINGS_PASSAGE_PREFIX", _preset_defaults()["passage_prefix"])


def embedding_query_prefix() -> str:
    return os.getenv("EMBEDDINGS_QUERY_PREFIX", _preset_defaults()["query_prefix"])


def embedding_normalize() -> bool:
    defaults = _preset_defaults()
    return _env_flag("EMBEDDINGS_NORMALIZE", defaults["normalize"])


def embedding_device_preference() -> str:
    return os.getenv("EMBEDDINGS_DEVICE", DEFAULT_DEVICE_PREF).strip().lower()


def embedding_wait_for_gpu() -> bool:
    return _env_flag("EMBEDDINGS_WAIT_FOR_GPU", DEFAULT_GPU_WAIT)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value
    except ValueError:
        return default


def embedding_gpu_min_free_mb() -> int:
    return _env_int("EMBEDDINGS_GPU_MIN_FREE_MB", DEFAULT_GPU_MIN_FREE_MB)


def embedding_gpu_max_retries() -> int:
    return max(0, _env_int("EMBEDDINGS_GPU_MAX_RETRIES", DEFAULT_GPU_MAX_RETRIES))


def embedding_gpu_retry_seconds() -> int:
    return max(1, _env_int("EMBEDDINGS_GPU_RETRY_SECONDS", DEFAULT_GPU_RETRY_SECONDS))
