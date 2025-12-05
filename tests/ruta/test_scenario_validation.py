from pathlib import Path

import pytest
import yaml

from llmc.ruta.types import Scenario


def test_validate_seed_scenarios():
    repo_root = Path(__file__).parents[2]
    usertests_dir = repo_root / "tests/usertests"
    
    assert usertests_dir.exists(), "tests/usertests directory not found"
    
    files = list(usertests_dir.glob("*.yaml"))
    assert len(files) > 0, "No scenario files found in tests/usertests"
    
    for scenario_file in files:
        with open(scenario_file) as f:
            data = yaml.safe_load(f)
            
        # Should not raise validation error
        try:
            scenario = Scenario(**data)
        except Exception as e:
            pytest.fail(f"Validation failed for {scenario_file.name}: {e}")
            
        assert scenario.id == data["id"]
        assert scenario.version == data["version"]
