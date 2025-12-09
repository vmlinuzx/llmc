"""
High-level chain CRUD operations for the config TUI.

Provides safe duplicate, delete, and reference tracking operations.
"""

import copy
from typing import Any


class ChainOperations:
    """High-level chain CRUD operations."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def duplicate_chain(self, chain_name: str, new_name: str) -> dict[str, Any]:
        """
        Create a copy of a chain definition with a new name.
        
        Returns the new chain dict (not yet added to config).
        Caller is responsible for adding it to config["enrichment"]["chain"].
        """
        chains = self.config.get("enrichment", {}).get("chain", [])
        
        # Find source chain
        source_chain = None
        for chain in chains:
            if chain.get("name") == chain_name:
                source_chain = chain
                break
        
        if source_chain is None:
            raise ValueError(f"Chain '{chain_name}' not found")
        
        # Check new name doesn't exist
        existing_names = {c.get("name") for c in chains}
        if new_name in existing_names:
            raise ValueError(f"Chain '{new_name}' already exists")
        
        # Create deep copy
        new_chain = copy.deepcopy(source_chain)
        new_chain["name"] = new_name
        
        return new_chain

    def delete_chain(self, chain_name: str) -> tuple[bool, list[str]]:
        """
        Check if a chain can be safely deleted.
        
        Returns:
            (can_delete, warnings/blockers)
            
        A chain can be deleted if:
        - It's not the only chain in a route
        - Or it's not referenced by any routes
        """
        chains = self.config.get("enrichment", {}).get("chain", [])
        routes = self.config.get("enrichment", {}).get("routes", {})
        
        # Find the chain
        target_chain = None
        for chain in chains:
            if chain.get("name") == chain_name:
                target_chain = chain
                break
        
        if target_chain is None:
            return False, [f"Chain '{chain_name}' not found"]
        
        chain_group = target_chain.get("chain")
        warnings = []
        
        # Get all chains in the same group
        siblings = [
            c for c in chains
            if c.get("chain") == chain_group and c.get("name") != chain_name
        ]
        
        # Check if this chain group is used in routes
        referencing_routes = [
            slice_type for slice_type, target in routes.items()
            if target == chain_group
        ]
        
        # Check for enabled siblings to ensure route viability
        enabled_siblings = [s for s in siblings if s.get("enabled", True)]
        
        if referencing_routes and len(enabled_siblings) == 0:
            # This is the ONLY enabled chain in a route - cannot delete
            return False, [
                f"Cannot delete: '{chain_name}' is the last ENABLED backend for route(s): "
                f"{', '.join(referencing_routes)}",
                f"Remaining siblings: {len(siblings)} (all disabled)"
            ]
        
        # Safe to delete, but add warnings
        if referencing_routes:
            warnings.append(
                f"⚠️  Chain group '{chain_group}' is used by routes: "
                f"{', '.join(referencing_routes)}"
            )
            warnings.append(
                f"   After deletion, {len(enabled_siblings)} enabled backend(s) will remain"
            )
        
        if not referencing_routes:
            warnings.append(
                f"✓ Chain '{chain_name}' is not referenced by any routes (orphaned)"
            )
        
        if not target_chain.get("enabled", True):
            warnings.append("ℹ️  Chain is currently disabled")
        
        return True, warnings

    def get_chain_references(self, chain_name: str) -> list[str]:
        """
        Find all routes referencing this chain's group.
        
        Returns list of slice_type names.
        """
        chains = self.config.get("enrichment", {}).get("chain", [])
        routes = self.config.get("enrichment", {}).get("routes", {})
        
        # Find chain group
        chain_group = None
        for chain in chains:
            if chain.get("name") == chain_name:
                chain_group = chain.get("chain")
                break
        
        if chain_group is None:
            return []
        
        # Find routes pointing to this chain group
        return [
            slice_type for slice_type, target in routes.items()
            if target == chain_group
        ]

    def get_cascade_order(self, chain_group: str) -> list[dict[str, Any]]:
        """
        Get all chains in a cascade, sorted by tier priority.
        
        Tier order: nano < 3b < 7b < 14b < 70b
        """
        chains = self.config.get("enrichment", {}).get("chain", [])
        
        # Filter to chain group
        group_chains = [
            chain for chain in chains
            if chain.get("chain") == chain_group
        ]
        
        # Define tier ordering
        tier_priority = {
            "nano": 0,
            "3b": 1,
            "7b": 2,
            "14b": 3,
            "70b": 4,
        }
        
        # Sort by tier, then by name for stability
        def sort_key(chain: dict[str, Any]) -> tuple[int, str]:
            tier = chain.get("routing_tier", "7b")
            priority = tier_priority.get(tier, 999)  # Unknown tiers go last
            return (priority, chain.get("name", ""))
        
        return sorted(group_chains, key=sort_key)

    def validate_tier_order(self, chain_group: str) -> list[str]:
        """
        Check if tier ordering makes sense (ascending).
        
        Returns list of warnings if tiers are out of order.
        """
        cascade = self.get_cascade_order(chain_group)
        
        if len(cascade) <= 1:
            return []  # Nothing to validate
        
        warnings = []
        tier_priority = {"nano": 0, "3b": 1, "7b": 2, "14b": 3, "70b": 4}
        
        prev_tier = None
        for chain in cascade:
            tier = chain.get("routing_tier")
            if prev_tier is not None:
                prev_priority = tier_priority.get(prev_tier, 0)
                curr_priority = tier_priority.get(tier, 0)
                
                if curr_priority < prev_priority:
                    warnings.append(
                        f"⚠️  Tier order: '{prev_tier}' → '{tier}' "
                        f"(expected ascending order)"
                    )
            prev_tier = tier
        
        return warnings
