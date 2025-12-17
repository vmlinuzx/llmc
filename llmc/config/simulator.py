"""
Routing simulator for testing enrichment routing decisions.

Simulates the routing logic to show what chain would be used for a given file.
"""

from pathlib import Path
from typing import Any


class RoutingSimulator:
    """Simulate routing decisions for test inputs."""

    # Map file extensions to slice types (mirrors actual router logic)
    SLICE_TYPE_MAP = {
        # Code files
        ".py": "code",
        ".js": "code",
        ".ts": "code",
        ".tsx": "code",
        ".jsx": "code",
        ".java": "code",
        ".kt": "code",
        ".rs": "code",
        ".go": "code",
        ".c": "code",
        ".cpp": "code",
        ".h": "code",
        ".hpp": "code",
        ".cs": "code",
        ".php": "code",
        ".rb": "code",
        ".swift": "code",
        ".scala": "code",
        # Documentation
        ".md": "docs",
        ".rst": "docs",
        ".txt": "docs",
        ".adoc": "docs",
        # Config
        ".toml": "config",
        ".yaml": "config",
        ".yml": "config",
        ".json": "config",
        ".ini": "config",
        ".conf": "config",
        # Data
        ".csv": "data",
        ".xml": "data",
        ".sql": "data",
    }

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def simulate_file(self, file_path: str) -> dict[str, Any]:
        """
        Simulate routing decision for a file path.

        Returns:
            {
                "file_path": str,
                "extension": str,
                "slice_type": str,
                "route_name": str | None,
                "chain_group": str,
                "backends": [
                    {
                        "name": str,
                        "tier": str,
                        "provider": str,
                        "model": str,
                        "url": str,
                        "enabled": bool
                    },
                    ...
                ]
            }
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        # Determine slice type
        slice_type = self.SLICE_TYPE_MAP.get(extension, "other")

        # Get routing configuration
        enrichment = self.config.get("enrichment", {})
        routes = enrichment.get("routes", {})
        default_chain = enrichment.get("default_chain", "athena")
        enable_routing = enrichment.get("enable_routing", False)

        # Determine chain group
        chain_group = default_chain
        route_name = None

        if enable_routing and slice_type in routes:
            chain_group = routes[slice_type]
            route_name = slice_type

        # Get all chains in the group, ordered by tier
        chains = enrichment.get("chain", [])
        group_chains = [c for c in chains if c.get("chain") == chain_group]

        # Sort by tier
        tier_priority = {"nano": 0, "3b": 1, "7b": 2, "14b": 3, "70b": 4}

        def sort_key(chain: dict[str, Any]) -> tuple[int, str]:
            tier = chain.get("routing_tier", "7b")
            priority = tier_priority.get(tier, 999)
            return (priority, chain.get("name", ""))

        group_chains = sorted(group_chains, key=sort_key)

        # Extract backend info
        backends = []
        for chain in group_chains:
            backends.append(
                {
                    "name": chain.get("name", "unknown"),
                    "tier": chain.get("routing_tier", "unknown"),
                    "provider": chain.get("provider", "unknown"),
                    "model": chain.get("model", "unknown"),
                    "url": chain.get("url", "N/A"),
                    "enabled": chain.get("enabled", True),
                }
            )

        return {
            "file_path": file_path,
            "extension": extension,
            "slice_type": slice_type,
            "route_name": route_name,
            "chain_group": chain_group,
            "backends": backends,
        }

    def list_slice_types(self) -> list[str]:
        """Get all possible slice types."""
        return sorted(set(self.SLICE_TYPE_MAP.values()) | {"other"})

    def get_unmapped_routes(self) -> list[str]:
        """
        Find routes defined in config that don't have corresponding slice types.

        This helps identify configuration errors.
        """
        enrichment = self.config.get("enrichment", {})
        routes = enrichment.get("routes", {})

        valid_types = self.list_slice_types()
        return [route for route in routes.keys() if route not in valid_types]
