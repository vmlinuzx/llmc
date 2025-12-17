"""
Configuration file manager for llmc.toml.

Handles loading, validation, backup, and safe writing of configuration files.
"""

from datetime import datetime
from pathlib import Path
import shutil
import tomllib
from typing import Any

try:
    import tomli_w
except ImportError:
    # Fallback to basic TOML writing if tomli_w not available
    import toml as tomli_w  # type: ignore


class ConfigManager:
    """Manages llmc.toml read/write/backup operations."""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

    def load(self) -> dict[str, Any]:
        """Load and parse llmc.toml."""
        with open(self.config_path, "rb") as f:
            self.config = tomllib.load(f)
        return self.config

    def save(self, config: dict[str, Any]) -> None:
        """Backup current config and write new one."""
        # Backup before writing
        backup_path = self.backup()

        try:
            # Write new config
            with open(self.config_path, "wb") as f:
                tomli_w.dump(config, f)
            self.config = config
        except Exception as e:
            # Restore from backup on failure
            if backup_path.exists():
                shutil.copy(backup_path, self.config_path)
            raise RuntimeError(f"Failed to save config: {e}") from e

    def backup(self) -> Path:
        """Create timestamped backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.with_suffix(f".toml.bak.{timestamp}")
        shutil.copy(self.config_path, backup_path)
        return backup_path

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Return list of validation errors.

        Performs basic structural validation:
        - Required sections exist
        - Chain names are unique
        - Route targets exist
        - Provider/tier values are valid
        """
        errors: list[str] = []

        # Check enrichment section exists
        if "enrichment" not in config:
            return ["Missing [enrichment] section"]

        enrichment = config["enrichment"]

        # Validate chains
        chains = enrichment.get("chain", [])
        if not isinstance(chains, list):
            errors.append("enrichment.chain must be an array of tables")
            return errors

        # Check for duplicate chain names
        chain_names = [c.get("name") for c in chains]
        duplicates = [name for name in chain_names if chain_names.count(name) > 1]
        if duplicates:
            errors.append(f"Duplicate chain names: {', '.join(set(duplicates))}")

        # Validate each chain
        for idx, chain in enumerate(chains):
            prefix = f"Chain #{idx + 1}"

            if "name" not in chain:
                errors.append(f"{prefix}: Missing 'name' field")
                continue

            name = chain["name"]
            prefix = f"Chain '{name}'"

            # Required fields
            required = ["chain", "provider", "model", "routing_tier"]
            for field in required:
                if field not in chain:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate provider (basic check, can enhance with allowed list)
            provider = chain.get("provider", "")
            if provider and not isinstance(provider, str):
                errors.append(f"{prefix}: Invalid provider type")

            # Validate tier
            tier = chain.get("routing_tier", "")
            allowed_tiers = ["nano", "3b", "7b", "14b", "70b"]
            if tier and tier not in allowed_tiers:
                errors.append(
                    f"{prefix}: Invalid routing_tier '{tier}' "
                    f"(allowed: {', '.join(allowed_tiers)})"
                )

        # Validate routes
        routes = enrichment.get("routes", {})
        chain_groups = {c.get("chain") for c in chains}

        for slice_type, target_chain in routes.items():
            if target_chain not in chain_groups:
                errors.append(
                    f"Route '{slice_type}' → '{target_chain}': "
                    f"Target chain group does not exist"
                )

        return errors

    def get_chains(self) -> list[dict[str, Any]]:
        """Get all enrichment chains."""
        return self.config.get("enrichment", {}).get("chain", [])

    def get_routes(self) -> dict[str, str]:
        """Get enrichment routes mapping."""
        return self.config.get("enrichment", {}).get("routes", {})

    def get_chain_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a chain by its name."""
        for chain in self.get_chains():
            if chain.get("name") == name:
                return chain
        return None

    def get_chains_by_group(self, chain_group: str) -> list[dict[str, Any]]:
        """Get all chains belonging to a chain group."""
        return [
            chain for chain in self.get_chains() if chain.get("chain") == chain_group
        ]
