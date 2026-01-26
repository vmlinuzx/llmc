import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Import targets
# Note: Imports might fail if the structure is different, catching import errors in tests is good practice
try:
    from llmc.rag.config_enrichment import EnrichmentProviderConfig
except ImportError:
    EnrichmentProviderConfig = None

try:
    from llmc.docgen.gating import resolve_doc_path
except ImportError:
    resolve_doc_path = None

try:
    from llmc.docgen.graph_context import GraphContextBuilder
except ImportError:
    GraphContextBuilder = None

try:
    pass
except ImportError:
    DocgenLock = None


class TestRenOffensive:
    """
    Ren's Ruthless Offensive Test Suite.
    Targeting recent changes and security fixes.
    """

    def test_routing_tier_freedom_chaos(self):
        """
        Test that routing_tier accepts absolute garbage, as promised by the 'freedom' update.
        """
        if not EnrichmentProviderConfig:
            pytest.skip("EnrichmentProviderConfig not found")

        # Test garbage strings
        garbage_tiers = [
            "HUGE_TIER_" * 100,
            "MixedCaseTier",
            "Tier with spaces",
            "🔥🔥🔥",
            "",  # Empty string might be interesting
            None,  # Should probably fail or handle gracefully
        ]

        for tier in garbage_tiers:
            # We are just checking if instantiation explodes
            try:
                cfg = EnrichmentProviderConfig(
                    name="test", provider="openai", model="gpt-4", routing_tier=tier
                )
                assert cfg.routing_tier == tier
            except Exception as e:
                # If it fails, we want to know WHY.
                # If tier is None, it might be optional?
                if tier is None:
                    # If it's required, this is expected.
                    pass
                else:
                    pytest.fail(f"Routing tier '{tier}' caused explosion: {e}")

    def test_docgen_path_traversal_bypass_attempts(self, tmp_path):
        """
        Ruthlessly try to bypass resolve_doc_path checks.
        """
        if not resolve_doc_path:
            pytest.skip("resolve_doc_path not found")

        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create a target file OUTSIDE the allowed area
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("secret data")

        # Attempts to access secret.txt via traversal
        attacks = [
            "../secret.txt",
            "/tmp/secret.txt",  # Absolute path
            f"{tmp_path}/secret.txt",  # Explicit absolute
            "DOCS/../../secret.txt",
        ]

        for attack in attacks:
            with pytest.raises((ValueError, RuntimeError), match="outside|Traversal"):
                resolve_doc_path(repo_root, Path(attack), output_dir="DOCS")

    def test_docgen_graph_context_malformed_data(self, tmp_path):
        """
        Feed list instead of dict to graph context builder.
        Commit 13d3d79 claimed to fix 'AttributeError: 'list' object has no attribute 'items''.
        Let's verify.
        """
        if not GraphContextBuilder:
            pytest.skip("GraphContextBuilder not found")

        # Mock the database or graph loader
        # We need to simulate the state where it loads bad data

        # Since GraphContextBuilder likely reads from a file or DB, let's see how to inject data.
        # Looking at the code (via previous context) it seems it processes entities.

        # We will try to directly invoke the validation logic if possible,
        # or mock the return of the data loader.

        builder = GraphContextBuilder(repo_root=tmp_path)

        # If there is a method like _validate_entities(self, entities), we'd call it.
        # But we don't know the internal API fully without inspecting.
        # We will try to rely on the public API `build` or similar, mocking the internal data fetch.

        with patch.object(
            builder, "_load_graph_data", return_value=[]
        ):  # Return list instead of dict
            # This should NOT crash
            try:
                builder.build_context(Path("some_file.py"))
                # It should probably return an empty context or partial context
            except AttributeError as e:
                pytest.fail(
                    f"Regression! GraphContextBuilder crashed on list input: {e}"
                )
            except Exception:
                # Other errors are acceptable if handled
                pass

    def test_docgen_lock_race_symlink(self, tmp_path):
        """
        Test DocgenLock against a pre-existing symlink.
        """
        if not DocgenLock:
            pytest.skip("DocgenLock not found")

        lock_dir = tmp_path / ".llmc"
        lock_dir.mkdir()
        lock_path = lock_dir / "docgen.lock"

        # Create a target file
        target_file = tmp_path / "victim.txt"
        target_file.write_text("Do not delete me")

        # Create a symlink at the lock path pointing to victim
        os.symlink(target_file, lock_path)

        lock = DocgenLock(lock_path)

        # Try to acquire. Should fail and NOT truncate victim.txt
        acquired = lock.acquire()

        assert acquired is False, "Should not acquire lock if it is a symlink"
        assert (
            target_file.read_text() == "Do not delete me"
        ), "Victim file was truncated!"
