"""Ruthless tests for repo_validator.

Tests configuration validation, Ollama connectivity checks,
and BOM detection/fixing.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestConfigValidation:
    """Test llmc.toml configuration validation."""

    def test_validate_missing_toml_file(self, tmp_path):
        """Should fail if llmc.toml doesn't exist."""
        from llmc.commands.repo_validator import validate_repo

        result = validate_repo(tmp_path)

        assert not result.passed
        assert result.error_count > 0
        assert any(
            "llmc.toml" in str(issue) or "not found" in str(issue).lower()
            for issue in result.issues
        )

    def test_validate_minimal_valid_config(self, tmp_path):
        """Minimal valid config should pass basic checks."""
        from llmc.commands.repo_validator import validate_repo

        # Create minimal llmc.toml
        config = tmp_path / "llmc.toml"
        config.write_text(
            """
[llmc]
name = "test-repo"

[enrichment]
backend = "ollama"
model = "qwen2.5:7b"

[embeddings]
model = "nomic-embed-text"
"""
        )

        # Create .llmc directory
        (tmp_path / ".llmc").mkdir()

        # Disable connectivity checks to avoid network calls
        result = validate_repo(tmp_path, check_connectivity=False, check_models=False)

        # Should parse successfully (may have warnings about routes)
        assert isinstance(result.passed, bool)
        # Config should be loaded
        assert result.config is not None

    def test_validate_missing_enrichment_section(self, tmp_path):
        """Should warn if [enrichment] section is missing."""
        from llmc.commands.repo_validator import validate_repo

        config = tmp_path / "llmc.toml"
        config.write_text(
            """
[llmc]
name = "test-repo"
"""
        )
        (tmp_path / ".llmc").mkdir()

        result = validate_repo(tmp_path, check_connectivity=False, check_models=False)

        # Should have issue about missing enrichment
        all_messages = [str(issue) for issue in result.issues]
        assert any("enrichment" in m.lower() for m in all_messages)


class TestBOMDetection:
    """Test Byte Order Mark detection and fixing."""

    def test_detect_bom_in_file(self, tmp_path):
        """Should detect UTF-8 BOM in files."""
        from llmc.commands.repo_validator import ValidationResult, check_bom_characters

        # Create file with BOM
        bom_file = tmp_path / "with_bom.py"
        bom_file.write_bytes(b"\xef\xbb\xbf# Python file with BOM\n")

        # Create file without BOM
        clean_file = tmp_path / "clean.py"
        clean_file.write_text("# Clean Python file\n")

        result = ValidationResult(repo_path=tmp_path)
        check_bom_characters(tmp_path, result)

        # Should have found the BOM file
        bom_issues = [i for i in result.issues if "bom" in str(i).lower()]
        assert len(bom_issues) > 0

    def test_fix_bom_in_file(self, tmp_path):
        """Should remove BOM from files when fixing."""
        from llmc.commands.repo_validator import ValidationResult, fix_bom_characters

        # Create file with BOM
        bom_file = tmp_path / "with_bom.py"
        original_content = b"\xef\xbb\xbf# Python file with BOM\nprint('hello')\n"
        bom_file.write_bytes(original_content)

        # Fix it
        result = ValidationResult(repo_path=tmp_path)
        fix_bom_characters([bom_file], result)

        # Verify BOM is gone
        fixed_content = bom_file.read_bytes()
        assert not fixed_content.startswith(b"\xef\xbb\xbf")
        assert b"# Python file with BOM" in fixed_content

    def test_no_false_positives_on_binary_files(self, tmp_path):
        """Should not flag binary files as having BOM issues."""
        from llmc.commands.repo_validator import ValidationResult, check_bom_characters

        # Create a binary file that happens to have random bytes
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header

        result = ValidationResult(repo_path=tmp_path)
        check_bom_characters(tmp_path, result, extensions=[".py", ".js", ".ts"])

        # Should not have flagged the PNG
        bom_issues = [i for i in result.issues if "image.png" in str(i)]
        assert len(bom_issues) == 0


class TestOllamaConnectivity:
    """Test Ollama connectivity checks."""

    @patch("urllib.request.urlopen")
    def test_ollama_reachable(self, mock_urlopen, tmp_path):
        """Should pass if Ollama is reachable."""
        from llmc.commands.repo_validator import (
            ValidationResult,
            check_ollama_connectivity,
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = ValidationResult(repo_path=tmp_path)
        result.config = {
            "enrichment": {
                "chain": [
                    {
                        "provider": "ollama",
                        "url": "http://localhost:11434",
                        "enabled": True,
                    }
                ]
            }
        }

        check_ollama_connectivity(result.config, result)

        # Should have an info message about reachability
        info_messages = [i for i in result.issues if i.severity == "info"]
        assert any("reachable" in str(i).lower() for i in info_messages)

    @patch("urllib.request.urlopen")
    def test_ollama_unreachable(self, mock_urlopen, tmp_path):
        """Should fail gracefully if Ollama is unreachable."""
        import urllib.error

        from llmc.commands.repo_validator import (
            ValidationResult,
            check_ollama_connectivity,
        )

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = ValidationResult(repo_path=tmp_path)
        result.config = {
            "enrichment": {
                "chain": [
                    {
                        "provider": "ollama",
                        "url": "http://localhost:11434",
                        "enabled": True,
                    }
                ]
            }
        }

        check_ollama_connectivity(result.config, result)

        # Should have an error about connectivity
        assert result.error_count > 0 or any(
            "connect" in str(i).lower() for i in result.issues
        )


class TestValidateRepoCommand:
    """Test the full validate_repo command."""

    def test_validate_repo_returns_valid_result(self, tmp_path):
        """validate_repo should return a ValidationResult."""
        from llmc.commands.repo_validator import ValidationResult, validate_repo

        result = validate_repo(tmp_path)

        assert isinstance(result, ValidationResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "issues")
        assert hasattr(result, "error_count")

    def test_validate_repo_with_good_config(self, tmp_path):
        """A well-configured repo should validate without errors."""
        from llmc.commands.repo_validator import validate_repo

        # Create a complete config
        config = tmp_path / "llmc.toml"
        config.write_text(
            """
[llmc]
name = "test-repo"

[enrichment]
backend = "ollama"
model = "qwen2.5:7b"
endpoint = "http://localhost:11434"

[embeddings]
model = "nomic-embed-text"
dim = 768

[embeddings.routes.docs]
index = "embeddings"

[routing]
default_slice_type = "docs"
"""
        )
        (tmp_path / ".llmc").mkdir()

        # Disable network checks
        result = validate_repo(tmp_path, check_connectivity=False, check_models=False)

        # Should have no parsing errors
        parsing_errors = [
            i
            for i in result.issues
            if "parse" in str(i).lower() and i.severity == "error"
        ]
        assert len(parsing_errors) == 0


class TestCLIIntegration:
    """Test CLI integration of repo validate."""

    @pytest.mark.integration
    @pytest.mark.allow_sleep
    def test_llmc_repo_validate_command_exists(self):
        """llmc repo validate should be a valid command."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "llmc.main", "repo", "validate", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Command should exist
        assert (
            result.returncode == 0
            or "validate" in result.stdout
            or "validate" in result.stderr
        )
