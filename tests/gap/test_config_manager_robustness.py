from copy import deepcopy
import shutil
from unittest.mock import patch

import pytest
import tomli_w

from llmc.config.manager import ConfigManager


class TestConfigManagerRobustness:

    @pytest.fixture
    def config_file(self, tmp_path):
        """Create a valid config file for testing."""
        config_content = {
            "enrichment": {
                "chain": [
                    {
                        "name": "default",
                        "chain": "basic",
                        "provider": "openai",
                        "model": "gpt-4o",
                        "routing_tier": "70b",
                    }
                ],
                "routes": {},
            }
        }
        fpath = tmp_path / "llmc.toml"
        with open(fpath, "wb") as f:
            tomli_w.dump(config_content, f)
        return fpath

    def test_save_happy_path(self, config_file):
        """
        Scenario 1: Happy Path
        Verify save() creates a backup and writes the new file correctly.
        """
        manager = ConfigManager(config_file)
        manager.load()

        new_config = deepcopy(manager.config)
        new_config["enrichment"]["chain"][0]["model"] = "gpt-3.5-turbo"

        # We need to spy on shutil.copy to verify backup was created
        with patch("shutil.copy", side_effect=shutil.copy) as mock_copy:
            manager.save(new_config)

            # Verify backup was called
            assert mock_copy.call_count >= 1

            # Verify new config was written
            manager_new = ConfigManager(config_file)
            loaded_config = manager_new.load()
            assert loaded_config["enrichment"]["chain"][0]["model"] == "gpt-3.5-turbo"

    def test_backup_failure(self, config_file):
        """
        Scenario 2: Backup Failure
        Mock shutil.copy to raise PermissionError.
        Verify save() aborts BEFORE touching the original file.
        """
        manager = ConfigManager(config_file)
        manager.load()
        original_content = config_file.read_bytes()

        new_config = deepcopy(manager.config)
        new_config["enrichment"]["chain"][0]["model"] = "gpt-3.5-turbo"

        with patch(
            "shutil.copy", side_effect=PermissionError("Mocked Permission Denied")
        ):
            with pytest.raises(PermissionError):
                manager.save(new_config)

        # Verify original file matches exactly (was not touched)
        assert config_file.read_bytes() == original_content

        # Verify internal state was NOT updated (optimistic update check)
        assert manager.config["enrichment"]["chain"][0]["model"] == "gpt-4o"

    def test_write_failure_disk_full(self, config_file):
        """
        Scenario 3: Write Failure (Disk Full)
        Mock tomli_w.dump to raise OSError.
        Verify:
        - Exception raised
        - Backup exists
        - Original file restored
        - Internal state not updated
        """
        manager = ConfigManager(config_file)
        manager.load()
        original_content = config_file.read_bytes()

        new_config = deepcopy(manager.config)
        new_config["enrichment"]["chain"][0]["model"] = "gpt-3.5-turbo"

        # We need to allow shutil.copy for backup, but fail the write
        # The 'save' method does: backup -> write -> restore if fail

        with patch("tomli_w.dump", side_effect=OSError("No space left on device")):
            with pytest.raises(RuntimeError) as excinfo:
                manager.save(new_config)
            assert "Failed to save config" in str(excinfo.value)

        # Verify backup exists
        backups = list(config_file.parent.glob("*.toml.bak.*"))
        assert len(backups) > 0

        # Verify original file content is restored
        assert config_file.read_bytes() == original_content

        # Verify internal state is not updated
        assert manager.config["enrichment"]["chain"][0]["model"] == "gpt-4o"

    def test_restoration_failure(self, config_file):
        """
        Scenario 4: Restoration Failure
        Simulate write failure followed by restoration failure.
        """
        manager = ConfigManager(config_file)
        manager.load()

        new_config = deepcopy(manager.config)
        new_config["enrichment"]["chain"][0]["model"] = "gpt-3.5-turbo"

        # We need to fail write (tomli_w.dump) AND fail the restoration (shutil.copy)
        real_copy = shutil.copy

        def copy_side_effect(src, dst):
            # First call is backup (src is config_file)
            if str(src) == str(config_file) and ".bak" in str(dst):
                return real_copy(src, dst)
            # Second call is restore (src is backup_path)
            raise PermissionError("Failed to restore")

        with (
            patch("tomli_w.dump", side_effect=OSError("Write failed")),
            patch("shutil.copy", side_effect=copy_side_effect),
        ):

            # Since the restore fails inside the except block of the write failure,
            # we expect the restore exception to propagate.
            with pytest.raises(PermissionError) as excinfo:
                manager.save(new_config)

            assert "Failed to restore" in str(excinfo.value)
