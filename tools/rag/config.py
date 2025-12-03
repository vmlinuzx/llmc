"""
Configuration helpers for RAG components: storage paths, embedding presets,
and reranker weights for RAG Nav search.
"""

from __future__ import annotations

import configparser
from functools import lru_cache
import logging
import os
from pathlib import Path
import tomllib
from typing import Any

# Conditional import for telemetry - allows the module to work without llmc dependency
try:
    from llmc.te.telemetry import log_routing_event
except ImportError:
    # No-op fallback when llmc module is not available
    def log_routing_event(
        mode: str, details: dict[str, Any], repo_root: Path | None = None
    ) -> None:
        """No-op fallback for telemetry logging when llmc module is unavailable."""
        pass


# Set up logging for this module
log = logging.getLogger(__name__)


# Custom exception for configuration errors
class ConfigError(Exception):
    """Custom exception for errors found in configuration."""

    pass


# Custom warning filter to log warnings only once per message
class ConfigWarningFilter(logging.Filter):
    """Filters out duplicate warning messages."""

    def __init__(self, name=""):
        super().__init__(name)
        self.seen = set()

    def filter(self, record):
        if record.levelno == logging.WARNING and record.msg in self.seen:
            return False
        self.seen.add(record.msg)
        return True


# Apply the filter to prevent log spam from config warnings
for handler in logging.root.handlers:
    handler.addFilter(ConfigWarningFilter())


RAG_DIR_NAME = ".rag"
DEFAULT_INDEX_NEW = "index_v2.db"
DEFAULT_INDEX_OLD = "index.db"
DEFAULT_SPANS_NAME = "spans.jsonl"
DEFAULT_EST_TOKENS_PER_SPAN = 350


def _find_repo_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return start


def find_repo_root(start: Path | None = None) -> Path:
    """
    Public wrapper for repository root detection.

    This keeps compatibility with older call sites that imported
    find_repo_root from this module while centralizing the logic in
    _find_repo_root.
    """
    return _find_repo_root(start)


@lru_cache
def load_config(repo_root: Path | None = None) -> dict:
    root = repo_root or _find_repo_root()
    path = root / "llmc.toml"
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_est_tokens_per_span(repo_root: Path | None = None) -> int:
    """
    Return the estimated number of tokens per enriched span.

    Precedence:
    - Environment variable LLMC_EST_TOKENS_PER_SPAN (if set and valid)
    - [enrichment].est_tokens_per_span in llmc.toml (if present and valid)
    - DEFAULT_EST_TOKENS_PER_SPAN constant as a final fallback.
    """
    env_value = os.getenv("LLMC_EST_TOKENS_PER_SPAN")
    if env_value is not None:
        try:
            parsed = int(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            # Ignore invalid env override and fall through to config/defaults.
            pass

    cfg = load_config(repo_root)
    enrichment_cfg = cfg.get("enrichment", {})
    raw_cfg_value = enrichment_cfg.get("est_tokens_per_span")
    if raw_cfg_value is not None:
        try:
            parsed = int(raw_cfg_value)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            # Ignore invalid config value and fall back to default.
            pass

    return DEFAULT_EST_TOKENS_PER_SPAN


def get_vacuum_interval_hours(repo_root: Path | None = None) -> int:
    """
    Return the vacuum interval in hours. Default is 24.

    Precedence:
    - Environment variable LLMC_RAG_VACUUM_INTERVAL_HOURS
    - [enrichment].vacuum_interval_hours in llmc.toml
    - Default: 24
    """
    env_value = os.getenv("LLMC_RAG_VACUUM_INTERVAL_HOURS")
    if env_value is not None:
        try:
            parsed = int(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            pass

    cfg = load_config(repo_root)
    enrichment_cfg = cfg.get("enrichment", {})
    raw_cfg_value = enrichment_cfg.get("vacuum_interval_hours")
    if raw_cfg_value is not None:
        try:
            parsed = int(raw_cfg_value)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass

    return 24


@lru_cache(maxsize=128)  # Cache to avoid log spam for repeated missing slice types
def get_route_for_slice_type(slice_type: str, repo_root: Path | None = None) -> str:
    """
    Determines the route_name for a given slice_type.
    Defaults to "docs" if the slice_type is not explicitly mapped.
    Emits a warning if a slice_type is unmapped, but only once per unique slice_type.
    """
    cfg = load_config(repo_root)
    slice_type_to_route = cfg.get("routing", {}).get("slice_type_to_route", {})

    route_name = slice_type_to_route.get(slice_type)
    if route_name is None:
        log.warning(
            f"Config: Missing 'routing.slice_type_to_route' entry for slice_type='{slice_type}'. "
            "Defaulting to route_name='docs'."
        )
        log_routing_event(
            mode="routing_fallback",
            details={
                "type": "missing_slice_type_mapping",
                "slice_type": slice_type,
                "fallback_to": "docs",
            },
            repo_root=repo_root,
        )
        return "docs"
    return str(route_name)


@lru_cache(maxsize=128)
def resolve_route(
    route_name: str, operation_type: str, repo_root: Path | None = None
) -> tuple[str, str]:
    """
    Resolves the embedding profile and index for a given route name.
    Handles missing route configurations and missing profile references with fallbacks or errors.

    Args:
        route_name: The name of the route (e.g., "docs", "code").
        operation_type: The type of operation ("ingest" or "query") for logging context.
        repo_root: The root path of the repository.

    Returns:
        A tuple containing (profile_name, index_name).

    Raises:
        ConfigError: If a critical configuration is missing and no fallback is possible.
    """
    cfg = load_config(repo_root)

    # 1. Check for missing embeddings.routes.* entries
    routes_cfg = cfg.get("embeddings", {}).get("routes", {})
    route_details = routes_cfg.get(route_name)

    # Fallback logic for missing route_name
    if route_details is None:
        if route_name != "docs":  # Avoid infinite recursion if "docs" route itself is missing
            log.warning(
                f"Config: Missing 'embeddings.routes.{route_name}' for {operation_type}. "
                "Falling back to 'docs' route."
            )
            log_routing_event(
                mode="routing_fallback",
                details={
                    "type": "missing_route_config",
                    "missing_route": route_name,
                    "operation": operation_type,
                    "fallback_to": "docs",
                },
                repo_root=repo_root,
            )
            return resolve_route("docs", operation_type, repo_root)
        else:  # "docs" route is missing, this is a critical error
            error_msg = (
                "Critical Config Error: 'embeddings.routes.docs' is missing, "
                "and no fallback is possible. Please define it in llmc.toml."
            )
            log.error(error_msg)
            log_routing_event(
                mode="routing_error",
                details={
                    "type": "critical_missing_docs_route",
                    "missing_route": "docs",
                    "operation": operation_type,
                    "error": error_msg,
                },
                repo_root=repo_root,
            )
            raise ConfigError(error_msg)

    profile_name = route_details.get("profile")
    index_name = route_details.get("index")

    if not profile_name or not index_name:
        if route_name != "docs":
            log.warning(
                f"Config: Route '{route_name}' for {operation_type} has incomplete definition "
                f"(profile: {profile_name}, index: {index_name}). Falling back to 'docs' route."
            )
            log_routing_event(
                mode="routing_fallback",
                details={
                    "type": "incomplete_route_definition",
                    "route": route_name,
                    "operation": operation_type,
                    "profile_missing": profile_name is None,
                    "index_missing": index_name is None,
                    "fallback_to": "docs",
                },
                repo_root=repo_root,
            )
            return resolve_route("docs", operation_type, repo_root)
        else:
            error_msg = (
                f"Critical Config Error: 'embeddings.routes.docs' is incompletely defined "
                f"(profile: {profile_name}, index: {index_name}). Please fix it in llmc.toml."
            )
            log.error(error_msg)
            log_routing_event(
                mode="routing_error",
                details={
                    "type": "critical_incomplete_docs_route",
                    "route": "docs",
                    "operation": operation_type,
                    "profile_missing": profile_name is None,
                    "index_missing": index_name is None,
                    "error": error_msg,
                },
                repo_root=repo_root,
            )
            raise ConfigError(error_msg)

    # 2. Check for missing embeddings.profiles.* entries
    profiles_cfg = cfg.get("embeddings", {}).get("profiles", {})
    profile_details = profiles_cfg.get(profile_name)

    if profile_details is None:
        if route_name == "docs":  # Fallback to default_docs only if the target route is "docs"
            log.warning(
                f"Config: Profile '{profile_name}' referenced by route '{route_name}' "
                f"for {operation_type} is missing. Attempting to use 'default_docs' profile."
            )
            log_routing_event(
                mode="routing_fallback",
                details={
                    "type": "missing_profile_reference",
                    "profile": profile_name,
                    "route": route_name,
                    "operation": operation_type,
                    "fallback_to": "default_docs",
                },
                repo_root=repo_root,
            )
            # This is a bit tricky: if 'default_docs' is also missing or its profile is missing,
            # resolve_route('docs') would handle the error or use its own fallback.
            # Here we assume 'default_docs' is a profile name, not a route name.
            default_docs_profile = profiles_cfg.get("default_docs")
            if default_docs_profile:
                return (
                    "default_docs",
                    index_name,
                )  # Use the default_docs profile but keep the index_name from the original route
            else:
                error_msg = (
                    f"Config Error: Route '{route_name}' for {operation_type} refers to missing profile "
                    f"'{profile_name}', and 'default_docs' profile is also missing. "
                    "Please define the profile or 'default_docs' in llmc.toml."
                )
                log.error(error_msg)
                log_routing_event(
                    mode="routing_error",
                    details={
                        "type": "critical_missing_profile_and_default",
                        "profile": profile_name,
                        "route": route_name,
                        "operation": operation_type,
                        "error": error_msg,
                    },
                    repo_root=repo_root,
                )
                raise ConfigError(error_msg)
        else:  # Cannot fallback for non-docs routes, raise error
            error_msg = (
                f"Config Error: Route '{route_name}' for {operation_type} refers to missing profile "
                f"'{profile_name}'. Please define the profile in llmc.toml."
            )
            log.error(error_msg)
            log_routing_event(
                mode="routing_error",
                details={
                    "type": "missing_profile_reference",
                    "profile": profile_name,
                    "route": route_name,
                    "operation": operation_type,
                    "error": error_msg,
                },
                repo_root=repo_root,
            )
            raise ConfigError(error_msg)

    return profile_name, index_name


def get_exclude_dirs(repo_root: Path | None = None) -> set[str]:
    cfg = load_config(repo_root)
    dirs = cfg.get("indexing", {}).get("exclude_dirs")
    if dirs:
        return set(dirs)
    return {
        ".git",
        ".rag",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".next",
        ".cache",
        ".pytest_cache",
        "coverage",
        ".DS_Store",
        "Thumbs.db",
    }


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


def _env_index_path(repo_root: Path) -> Path | None:
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
    return int(_preset_defaults()["dim"])


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


def embedding_gpu_min_free_mb(repo_root: Path | None = None) -> int:
    cfg = load_config(repo_root)
    val = cfg.get("embeddings", {}).get("gpu_min_free_mb")
    if val is not None:
        return int(val)
    return _env_int("EMBEDDINGS_GPU_MIN_FREE_MB", DEFAULT_GPU_MIN_FREE_MB)


def is_query_routing_enabled(repo_root: Path | None = None) -> bool:
    cfg = load_config(repo_root)
    # Default to False if the flag is omitted (backwards-compatible behavior)
    return bool(cfg.get("routing", {}).get("options", {}).get("enable_query_routing", False))


def is_multi_route_enabled(repo_root: Path | None = None) -> bool:
    cfg = load_config(repo_root)
    return bool(cfg.get("routing", {}).get("options", {}).get("enable_multi_route", False))


def get_multi_route_config(
    primary_route: str, repo_root: Path | None = None
) -> list[tuple[str, float]]:
    """
    Returns a list of (route_name, weight) tuples for the given primary route.
    Always includes the primary route itself with weight 1.0.
    If multi-route is disabled or no config exists, returns just the primary route.
    """
    # Always start with the primary route
    routes = [(primary_route, 1.0)]

    if not is_multi_route_enabled(repo_root):
        return routes

    cfg = load_config(repo_root)
    multi_route_cfg = cfg.get("routing", {}).get("multi_route", {})

    # Look for config specifically for this primary route (e.g., "code_primary")
    primary_key = f"{primary_route}_primary"
    route_cfg = multi_route_cfg.get(primary_key)

    if not route_cfg:
        return routes

    # Verify the config actually matches the primary route we expect
    if route_cfg.get("primary") != primary_route:
        log.warning(
            f"Config: Mismatch in multi-route config for '{primary_key}'. "
            f"Expected primary='{primary_route}', found '{route_cfg.get('primary')}'. "
            "Ignoring secondary routes."
        )
        return routes

    # Add secondary routes
    secondaries = route_cfg.get("secondary", [])
    for sec in secondaries:
        r_name = sec.get("route")
        weight = sec.get("weight", 1.0)
        if r_name:
            routes.append((r_name, float(weight)))

    return routes


def embedding_gpu_max_retries() -> int:
    return max(0, _env_int("EMBEDDINGS_GPU_MAX_RETRIES", DEFAULT_GPU_MAX_RETRIES))


def embedding_gpu_retry_seconds() -> int:
    return max(1, _env_int("EMBEDDINGS_GPU_RETRY_SECONDS", DEFAULT_GPU_RETRY_SECONDS))


# --- Reranker configuration for RAG Nav --------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "bm25": 0.60,
    "uni": 0.20,
    "bi": 0.15,
    "path": 0.03,
    "lit": 0.02,
}

ENV_KEYS: dict[str, str] = {
    "bm25": "RAG_RERANK_W_BM25",
    "uni": "RAG_RERANK_W_UNI",
    "bi": "RAG_RERANK_W_BI",
    "path": "RAG_RERANK_W_PATH",
    "lit": "RAG_RERANK_W_LIT",
}

INI_SECTION = "rerank"  # Section name in .llmc/rag_nav.ini


def _parse_float(value: str, default: float) -> float:
    """Convert value to float, falling back to default on error."""
    try:
        return float(value)
    except Exception:
        return default


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    """Normalize non-negative weights so they sum to 1.0."""
    total = sum(max(0.0, v) for v in weights.values())
    if total <= 0.0:
        return dict(DEFAULT_WEIGHTS)
    return {key: max(0.0, value) / total for key, value in weights.items()}


def load_rerank_weights(repo_root: Path | None = None) -> dict[str, float]:
    """
    Load reranker weights from `.llmc/rag_nav.ini` and environment overrides.

    Precedence:
    - Defaults in DEFAULT_WEIGHTS
    - Values from `[rerank]` section in `.llmc/rag_nav.ini` under repo_root
    - Environment variables (RAG_RERANK_W_*)
    """
    weights: dict[str, float] = dict(DEFAULT_WEIGHTS)

    # INI file (if present)
    if repo_root is not None:
        ini_path = Path(repo_root) / ".llmc" / "rag_nav.ini"
        if ini_path.exists():
            parser = configparser.ConfigParser()
            try:
                parser.read(ini_path)
                if INI_SECTION in parser:
                    section = parser[INI_SECTION]
                    for key in list(weights.keys()):
                        if key in section:
                            weights[key] = _parse_float(section.get(key, ""), weights[key])
            except Exception:
                # Treat config errors as "use defaults".
                pass

    # Environment overrides
    for key, env_name in ENV_KEYS.items():
        value = os.environ.get(env_name)
        if value is not None and value.strip() != "":
            weights[key] = _parse_float(value, weights[key])

    return _normalize(weights)
