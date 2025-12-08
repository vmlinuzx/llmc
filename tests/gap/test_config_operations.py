import pytest
from llmc.config.operations import ChainOperations

class TestChainOperations:
    
    def test_deep_copy_verification(self):
        """
        Test that duplicate_chain performs a deep copy.
        This ensures modifying the new chain's nested structures doesn't affect the old one.
        """
        initial_config = {
            "enrichment": {
                "chain": [
                    {
                        "name": "source-chain",
                        "chain": "group1",
                        "routing_tier": "nano",
                        "parameters": {"temp": 0.7}
                    }
                ]
            }
        }
        
        ops = ChainOperations(initial_config)
        
        # Duplicate the chain
        new_chain = ops.duplicate_chain("source-chain", "new-chain")
        
        # Modify nested data in the new chain
        new_chain["parameters"]["temp"] = 0.9
        
        # Verify the old chain is unchanged
        source_chain = initial_config["enrichment"]["chain"][0]
        assert source_chain["parameters"]["temp"] == 0.7, \
            "Source chain was modified! duplicate_chain failed to perform deep copy."

    def test_tier_sorting(self):
        """
        Test that get_cascade_order sorts tiers correctly, with unknown tiers last.
        """
        initial_config = {
            "enrichment": {
                "chain": [
                    {"name": "c1", "chain": "g1", "routing_tier": "70b"},
                    {"name": "c2", "chain": "g1", "routing_tier": "nano"},
                    {"name": "c3", "chain": "g1", "routing_tier": "custom-8b"}, # Unknown
                    {"name": "c4", "chain": "g1", "routing_tier": "7b"},
                ]
            }
        }
        
        ops = ChainOperations(initial_config)
        
        # Get cascade order
        cascade = ops.get_cascade_order("g1")
        
        # Extract names to verify order
        ordered_names = [c["name"] for c in cascade]
        
        # Expected order: nano (0), 7b (2), 70b (4), custom-8b (999/last)
        expected_order = ["c2", "c4", "c1", "c3"]
        
        assert ordered_names == expected_order, f"Tier sorting incorrect. Got {ordered_names}, expected {expected_order}"

    def test_safe_deletion_unique_in_route(self):
        """
        Scenario A: Chain is unique in group, used by route -> Delete blocked.
        """
        initial_config = {
            "enrichment": {
                "chain": [
                    {"name": "c1", "chain": "g1", "enabled": True}
                ],
                "routes": {
                    "summary": "g1"
                }
            }
        }
        
        ops = ChainOperations(initial_config)
        can_delete, warnings = ops.delete_chain("c1")
        
        assert can_delete is False, "Should block deletion when chain is the only one in a route group"
        assert any("only backend" in w for w in warnings)

    def test_safe_deletion_siblings_disabled(self):
        """
        Scenario B: Chain has siblings, but all siblings are enabled=False.
        The SDD suggests this should probably warn or block.
        Currently checking if it blocks (expecting failure if implementation isn't safe).
        """
        initial_config = {
            "enrichment": {
                "chain": [
                    {"name": "c1", "chain": "g1", "enabled": True},
                    {"name": "c2", "chain": "g1", "enabled": False} # Sibling disabled
                ],
                "routes": {
                    "summary": "g1"
                }
            }
        }
        
        ops = ChainOperations(initial_config)
        can_delete, warnings = ops.delete_chain("c1")
        
        # We assert strictly for safety, knowing this might fail the test on current implementation
        assert can_delete is False, \
            "Should block deletion when all remaining siblings are disabled"

    def test_safe_deletion_unused(self):
        """
        Scenario C: Chain is not used by any route -> Delete allowed.
        """
        initial_config = {
            "enrichment": {
                "chain": [
                    {"name": "c1", "chain": "g1", "enabled": True}
                ],
                "routes": {
                    "summary": "other_group"
                }
            }
        }
        
        ops = ChainOperations(initial_config)
        can_delete, warnings = ops.delete_chain("c1")
        
        assert can_delete is True, "Should allow deletion when chain is not used by any route"
        assert any("orphaned" in w for w in warnings)
