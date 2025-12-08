import pytest
from pathlib import Path
from llmc.core import load_config

def test_load_config_malformed_raises_error(tmp_path):
    """
    Gap: load_config currently suppresses parsing errors.
    Target behavior: It should raise an error so the user knows their config is broken.
    """
    # Setup
    bad_config = tmp_path / "llmc.toml"
    bad_config.write_text("this is not [valid toml", encoding="utf-8")
    
    # Execution & Assertion
    # This assertion is expected to FAIL currently, exposing the gap.
    with pytest.raises(Exception):
        load_config(tmp_path)
