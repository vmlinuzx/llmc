#!/usr/bin/env python3
"""
End-to-end test for Architect Concise Mode system.

Tests:
1. Prompt file loads correctly
2. Example spec validates successfully
3. Parser extracts structured data
4. Invalid specs are caught
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent  # Test file is at repo root
sys.path.insert(0, str(project_root))

from scripts.validate_architect_spec import ArchitectSpecValidator


def test_prompt_exists():
    """Test that prompt file exists and loads."""
    prompt_path = project_root / "prompts" / "system_architect_concise.md"
    print(f"Looking for prompt at: {prompt_path}")
    assert prompt_path.exists(), f"Prompt not found: {prompt_path}"
    
    content = prompt_path.read_text()
    assert len(content) > 100, "Prompt content too short"
    assert "### GOAL" in content, "Schema sections missing"
    assert "### FILES" in content
    assert "### FUNCS" in content
    print("✅ Prompt file loads correctly")


def test_example_spec_validates():
    """Test that example spec passes validation."""
    example_path = project_root / "examples" / "specs" / "auth_feature_example.md"
    assert example_path.exists(), f"Example not found: {example_path}"
    
    content = example_path.read_text()
    validator = ArchitectSpecValidator(content)
    is_valid, errors, warnings = validator.validate()
    
    assert is_valid, f"Example spec invalid: {errors}"
    assert len(errors) == 0, f"Unexpected errors: {errors}"
    print(f"✅ Example spec validates (0 errors, {len(warnings)} warnings)")


def test_parser_extracts_data():
    """Test that we can parse structured data from spec."""
    example_path = project_root / "examples" / "specs" / "auth_feature_example.md"
    content = example_path.read_text()
    
    # Parse sections
    sections = {}
    current_section = None
    for line in content.split('\n'):
        if line.startswith("### "):
            current_section = line[4:].strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
    
    # Verify sections
    required = ["GOAL", "FILES", "FUNCS", "POLICY", "TESTS", "RUNBOOK", "RULES"]
    for section in required:
        assert section in sections, f"Missing section: {section}"
    
    # Verify we can extract files
    files_section = sections["FILES"]
    create_files = [line for line in files_section if "[CREATE]" in line]
    assert len(create_files) > 0, "No CREATE files found"
    
    # Verify we can extract functions
    funcs_section = sections["FUNCS"]
    functions = [line for line in funcs_section if "→" in line]
    assert len(functions) > 0, "No functions found"
    
    print(f"✅ Parser extracts data ({len(create_files)} files, {len(functions)} funcs)")


def test_invalid_spec_caught():
    """Test that invalid specs are caught."""
    invalid_spec = """
# Invalid Spec

This is prose instead of bullet points.

### GOAL
Add authentication

### FILES
Missing action verb format

### FUNCS
Missing return type arrows
"""
    
    validator = ArchitectSpecValidator(invalid_spec)
    is_valid, errors, warnings = validator.validate()
    
    assert not is_valid, "Invalid spec was not caught"
    assert len(errors) > 0, "No errors reported for invalid spec"
    print(f"✅ Invalid spec caught ({len(errors)} errors)")


def test_token_budget_enforced():
    """Test that excessive tokens are flagged."""
    # Create a spec that's way too long
    long_spec = """
### GOAL
This is a very long goal that exceeds the 80 character limit significantly

### FILES
""" + "\n".join([f"- file{i}.py [CREATE] - description" for i in range(200)])
    
    long_spec += """

### FUNCS
""" + "\n".join([f"- func{i}() → None - purpose" for i in range(200)])
    
    long_spec += """

### POLICY
- Rule 1
### TESTS
- Test 1
### RUNBOOK
1. Step 1
### RULES
- NO prose
"""
    
    validator = ArchitectSpecValidator(long_spec)
    is_valid, errors, warnings = validator.validate()
    
    # Should have warnings or errors about length
    assert len(errors) > 0 or len(warnings) > 0, "Token budget not enforced"
    print(f"✅ Token budget enforced ({len(errors)} errors, {len(warnings)} warnings)")


def main():
    """Run all tests."""
    print("=" * 60)
    print("ARCHITECT CONCISE MODE - END-TO-END TEST")
    print("=" * 60)
    print()
    
    try:
        test_prompt_exists()
        test_example_spec_validates()
        test_parser_extracts_data()
        test_invalid_spec_caught()
        test_token_budget_enforced()
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
