"""Tests for RLM config loading."""
import pytest
from pathlib import Path
import tempfile
import sys

# Ensure compatibility with python < 3.11
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from llmc.rlm.config import load_rlm_config, RLMConfig


class TestLoadRLMConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        """No llmc.toml → all defaults."""
        config = load_rlm_config(tmp_path / "nonexistent.toml")
        assert config.root_model == "ollama_chat/qwen3-next-80b"
        assert config.max_session_budget_usd == 1.00

    def test_missing_rlm_section_returns_defaults(self, tmp_path):
        """llmc.toml exists but no [rlm] section → defaults."""
        (tmp_path / "llmc.toml").write_text("[enrichment]\nmodel = 'foo'\n")
        config = load_rlm_config(tmp_path / "llmc.toml")
        assert config.max_subcall_depth == 5

    def test_partial_config_merges_with_defaults(self, tmp_path):
        """Partial [rlm] merges with defaults."""
        (tmp_path / "llmc.toml").write_text('[rlm]\nroot_model = "custom/model"\n')
        config = load_rlm_config(tmp_path / "llmc.toml")
        assert config.root_model == "custom/model"
        assert config.sub_model == "ollama_chat/qwen3-next-80b"  # Default

    def test_sandbox_config_applied(self, tmp_path):
        """[rlm.sandbox] blocked_builtins applied."""
        toml = '''
[rlm.sandbox]
blocked_builtins = ["open", "exec"]
allowed_modules = ["json"]
'''
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        assert "open" in config.blocked_builtins
        assert "json" in config.allowed_modules
        assert "math" not in config.allowed_modules # Should be overwritten

    def test_negative_budget_raises_valueerror(self, tmp_path):
        """Negative budget → ValueError."""
        (tmp_path / "llmc.toml").write_text('[rlm]\nmax_session_budget_usd = -1.0\n')
        
        # load_rlm_config calls validate()
        with pytest.raises(ValueError, match="cannot be negative"):
            load_rlm_config(tmp_path / "llmc.toml")

    def test_invalid_type_handling(self, tmp_path):
        """String where int expected → should raise error or fail validation."""
        # dataclasses.replace might accept it, but type hints are just hints.
        # However, our validate method might catch some, or runtime errors later.
        # The SDD says "TypeError, ValueError".
        # dataclasses.replace does NOT validation types by default.
        # But if we use it, it will just store the string.
        # So we'll need to rely on validation or explicit casting (which we didn't implement).
        # Let's see what happens.
        
        (tmp_path / "llmc.toml").write_text('[rlm]\ncode_timeout_seconds = "fast"\n')
        
        # If we didn't implement strict type checking, this might pass the loader 
        # but fail validate() if we check types, or fail later.
        # RLMConfig validate() only checks values:
        # if self.code_timeout_seconds < 1: ...
        # "fast" < 1 will raise TypeError in Python 3.
        
        with pytest.raises(TypeError):
            load_rlm_config(tmp_path / "llmc.toml")

    def test_unknown_keys_ignored(self, tmp_path):
        """Unknown keys in [rlm] are ignored (no error)."""
        (tmp_path / "llmc.toml").write_text('[rlm]\nunknown_future_key = 42\n')
        config = load_rlm_config(tmp_path / "llmc.toml")
        assert not hasattr(config, "unknown_future_key")


class TestNestedConfigParsing:
    """Tests for nested TOML section parsing (Phase 1.X)."""
    
    def test_nested_budget_parsing(self, tmp_path):
        """[rlm.budget] section should parse correctly."""
        toml = """
[rlm.budget]
max_session_budget_usd = 2.50
max_session_tokens = 100000
soft_limit_percentage = 0.75
max_subcall_depth = 3
"""
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        
        assert config.max_session_budget_usd == 2.50
        assert config.max_tokens_per_session == 100000
        assert config.soft_limit_percentage == 0.75
        assert config.max_subcall_depth == 3
    
    def test_nested_sandbox_parsing(self, tmp_path):
        """[rlm.sandbox] section should parse all keys."""
        toml = """
[rlm.sandbox]
backend = "restricted"
security_mode = "restrictive"
code_timeout_seconds = 15
blocked_builtins = ["open", "exec"]
allowed_modules = ["json", "math"]
"""
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        
        assert config.sandbox_backend == "restricted"
        assert config.security_mode == "restrictive"
        assert config.code_timeout_seconds == 15
        assert "open" in config.blocked_builtins
        assert "json" in config.allowed_modules
        assert len(config.allowed_modules) == 2
    
    def test_nested_llm_params(self, tmp_path):
        """[rlm.llm.root] and [rlm.llm.sub] should parse."""
        toml = """
[rlm.llm.root]
temperature = 0.3
max_tokens = 8192

[rlm.llm.sub]
temperature = 0.05
max_tokens = 512
"""
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        
        assert config.root_temperature == 0.3
        assert config.root_max_tokens == 8192
        assert config.sub_temperature == 0.05
        assert config.sub_max_tokens == 512
    
    def test_nested_session_and_trace(self, tmp_path):
        """[rlm.session] and [rlm.trace] should parse."""
        toml = """
[rlm.session]
max_turns = 15
session_timeout_seconds = 600
max_context_chars = 500000

[rlm.trace]
enabled = false
prompt_preview_chars = 100
response_preview_chars = 150
"""
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        
        assert config.max_turns == 15
        assert config.session_timeout_seconds == 600
        assert config.max_context_chars == 500000
        assert config.trace_enabled == False
        assert config.prompt_preview_chars == 100
        assert config.response_preview_chars == 150
    
    def test_load_restrictive_fixture(self, tmp_path):
        """Load restrictive fixture and verify nested values."""
        from pathlib import Path as P; fixture_path = P(__file__).parent.parent / "fixtures" / "rlm_config_restrictive.toml"; config = load_rlm_config(fixture_path)
        
        # From [rlm]
        assert config.root_model == "deepseek/deepseek-reasoner"
        
        # From [rlm.budget]
        assert config.max_session_budget_usd == 0.10
        assert config.max_tokens_per_session == 50000
        assert config.soft_limit_percentage == 0.70
        
        # From [rlm.sandbox]
        assert config.security_mode == "restrictive"
        assert config.code_timeout_seconds == 10
        assert len(config.allowed_modules) == 3
    
    def test_nested_overrides_defaults(self, tmp_path):
        """Nested values should override defaults."""
        toml = """
[rlm.budget]
max_session_budget_usd = 0.50
"""
        (tmp_path / "llmc.toml").write_text(toml)
        config = load_rlm_config(tmp_path / "llmc.toml")
        
        # Nested value overridden
        assert config.max_session_budget_usd == 0.50
        
        # Other budget fields should still be defaults
        assert config.max_tokens_per_session == 500_000
        assert config.max_subcall_depth == 5
