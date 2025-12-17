from pathlib import Path
import tomllib

VALID_DOMAINS = {"code", "tech_docs", "legal", "medical", "mixed"}


def lint_config(config_path: str) -> tuple[bool, list[str]]:
    """Lint llmc.toml for tech docs config.

    Returns:
        (passed, errors) tuple
    """
    errors = []
    path = Path(config_path)
    if not path.exists():
        return False, [f"Config file not found: {config_path}"]

    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        return False, [f"Invalid TOML: {e}"]

    # Check for [repository] section
    if "repository" not in config:
        errors.append("Missing [repository] section")
    else:
        repo_config = config["repository"]

        # Check domain value is valid
        domain = repo_config.get("domain")
        if domain is not None and domain not in VALID_DOMAINS:
            errors.append(
                f"Invalid domain: '{domain}'. Must be one of {sorted(VALID_DOMAINS)}"
            )

        # Check path_overrides if present
        path_overrides = repo_config.get("path_overrides")
        if path_overrides:
            if not isinstance(path_overrides, dict):
                errors.append("path_overrides must be a dictionary")
            else:
                for pattern, override_domain in path_overrides.items():
                    if override_domain not in VALID_DOMAINS:
                        errors.append(
                            f"Invalid domain in path_overrides: '{override_domain}' for pattern '{pattern}'"
                        )

    return len(errors) == 0, errors
