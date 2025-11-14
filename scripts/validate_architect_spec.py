#!/usr/bin/env python3
"""
Validate SYSTEM ARCHITECT (CONCISE MODE) output against schema.

Usage:
    python scripts/validate_architect_spec.py <spec_file>
    
Example:
    python scripts/validate_architect_spec.py specs/auth_feature.md
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ArchitectSpecValidator:
    """Validates architect specs against the concise schema."""
    
    # Required sections in order
    REQUIRED_SECTIONS = ["GOAL", "FILES", "FUNCS", "POLICY", "TESTS", "RUNBOOK", "RULES"]
    
    # Valid file actions
    VALID_ACTIONS = ["CREATE", "MODIFY", "DELETE", "RENAME"]
    
    # Style limits
    MAX_LINE_LENGTH = 80
    MAX_TOKENS = 1000  # Approximate
    TARGET_TOKENS = 900
    
    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.sections: Dict[str, List[str]] = {}
        
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations. Returns (is_valid, errors, warnings)."""
        self._parse_sections()
        self._validate_required_sections()
        self._validate_goal()
        self._validate_files()
        self._validate_funcs()
        self._validate_policy()
        self._validate_tests()
        self._validate_runbook()
        self._validate_rules()
        self._validate_line_lengths()
        self._validate_token_count()
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _parse_sections(self):
        """Parse content into sections."""
        current_section = None
        current_lines = []
        
        for line in self.lines:
            # Check if line is a section header
            if line.startswith("### "):
                if current_section:
                    self.sections[current_section] = current_lines
                current_section = line[4:].strip()
                current_lines = []
            elif current_section:
                current_lines.append(line)
        
        # Add last section
        if current_section:
            self.sections[current_section] = current_lines
    
    def _validate_required_sections(self):
        """Check all required sections are present in order."""
        found_sections = [s for s in self.REQUIRED_SECTIONS if s in self.sections]
        
        if len(found_sections) < len(self.REQUIRED_SECTIONS):
            missing = set(self.REQUIRED_SECTIONS) - set(found_sections)
            self.errors.append(f"Missing sections: {', '.join(missing)}")
        
        # Check order
        section_order = list(self.sections.keys())
        required_positions = {s: i for i, s in enumerate(self.REQUIRED_SECTIONS)}
        
        for i, section in enumerate(section_order):
            if section in required_positions:
                expected_pos = required_positions[section]
                if i < expected_pos:
                    self.warnings.append(
                        f"Section '{section}' appears out of order (expected after position {expected_pos})"
                    )
    
    def _validate_goal(self):
        """Validate GOAL section."""
        if "GOAL" not in self.sections:
            return
        
        goal_lines = [l.strip() for l in self.sections["GOAL"] if l.strip()]
        
        if not goal_lines:
            self.errors.append("GOAL section is empty")
            return
        
        if len(goal_lines) > 1:
            self.warnings.append("GOAL should be single line")
        
        goal = goal_lines[0]
        if len(goal) > self.MAX_LINE_LENGTH:
            self.errors.append(f"GOAL exceeds {self.MAX_LINE_LENGTH} chars: {len(goal)}")
    
    def _validate_files(self):
        """Validate FILES section."""
        if "FILES" not in self.sections:
            return
        
        file_pattern = re.compile(r'^-\s+([^\s]+)\s+\[(' + '|'.join(self.VALID_ACTIONS) + r')\]\s+-\s+.+$')
        
        for line in self.sections["FILES"]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if not file_pattern.match(line):
                self.errors.append(f"Invalid FILES entry: {line}")
                self.warnings.append(
                    f"Expected format: '- path/to/file [ACTION] - description'"
                )
            
            # Check if description is too long
            if ' - ' in line:
                description = line.split(' - ', 1)[1]
                if len(description) > 40:
                    self.warnings.append(
                        f"FILES description too long (>40 chars): {line}"
                    )
    
    def _validate_funcs(self):
        """Validate FUNCS section."""
        if "FUNCS" not in self.sections:
            return
        
        # Pattern: - module.function(args) → type - description
        func_pattern = re.compile(r'^-\s+[\w\.]+\([^\)]*\)\s+→\s+[\w\|\s]+\s+-\s+.+$')
        
        for line in self.sections["FUNCS"]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if not func_pattern.match(line):
                self.warnings.append(f"Possible invalid FUNCS entry: {line}")
                self.warnings.append(
                    "Expected format: '- module.func(args) → ReturnType - description'"
                )
    
    def _validate_policy(self):
        """Validate POLICY section."""
        if "POLICY" not in self.sections:
            return
        
        for line in self.sections["POLICY"]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if not line.startswith('- '):
                self.warnings.append(f"POLICY should use bullet points: {line}")
            
            # Check length
            clean_line = line[2:] if line.startswith('- ') else line
            if len(clean_line) > 60:
                self.warnings.append(f"POLICY item too long (>60 chars): {line}")
    
    def _validate_tests(self):
        """Validate TESTS section."""
        if "TESTS" not in self.sections:
            return
        
        for line in self.sections["TESTS"]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if not line.startswith('- '):
                self.warnings.append(f"TESTS should use bullet points: {line}")
            
            # Check length
            clean_line = line[2:] if line.startswith('- ') else line
            if len(clean_line) > 60:
                self.warnings.append(f"TEST item too long (>60 chars): {line}")
    
    def _validate_runbook(self):
        """Validate RUNBOOK section."""
        if "RUNBOOK" not in self.sections:
            return
        
        step_pattern = re.compile(r'^\d+\.\s+.+$')
        
        for line in self.sections["RUNBOOK"]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if not step_pattern.match(line):
                self.warnings.append(f"RUNBOOK should use numbered steps: {line}")
            
            # Check length
            if len(line) > self.MAX_LINE_LENGTH:
                self.warnings.append(f"RUNBOOK step too long (>{self.MAX_LINE_LENGTH} chars): {line}")
    
    def _validate_rules(self):
        """Validate RULES section."""
        if "RULES" not in self.sections:
            return
        
        # RULES section should just restate the key constraints
        # No specific validation needed beyond general format
        pass
    
    def _validate_line_lengths(self):
        """Check that most lines are within length limit."""
        long_lines = []
        
        for i, line in enumerate(self.lines, 1):
            line = line.rstrip()
            if line.startswith('#'):  # Skip headers
                continue
            
            if len(line) > self.MAX_LINE_LENGTH:
                long_lines.append((i, len(line), line[:60] + "..."))
        
        if long_lines:
            self.warnings.append(
                f"{len(long_lines)} lines exceed {self.MAX_LINE_LENGTH} chars"
            )
            # Show first 3
            for line_no, length, preview in long_lines[:3]:
                self.warnings.append(f"  Line {line_no} ({length} chars): {preview}")
    
    def _validate_token_count(self):
        """Estimate token count (rough approximation)."""
        # Rough estimate: 1 token ≈ 4 characters
        char_count = len(self.content)
        estimated_tokens = char_count // 4
        
        if estimated_tokens > self.MAX_TOKENS:
            self.errors.append(
                f"Token count exceeds limit: ~{estimated_tokens} (max: {self.MAX_TOKENS})"
            )
        elif estimated_tokens > self.TARGET_TOKENS:
            self.warnings.append(
                f"Token count above target: ~{estimated_tokens} (target: {self.TARGET_TOKENS})"
            )
        else:
            # This is good news
            pass
    
    def generate_report(self) -> str:
        """Generate human-readable validation report."""
        report = []
        report.append("=" * 60)
        report.append("ARCHITECT SPEC VALIDATION REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Summary
        is_valid = len(self.errors) == 0
        status = "✅ VALID" if is_valid else "❌ INVALID"
        report.append(f"Status: {status}")
        report.append(f"Errors: {len(self.errors)}")
        report.append(f"Warnings: {len(self.warnings)}")
        report.append("")
        
        # Sections found
        report.append("Sections Found:")
        for section in self.sections.keys():
            marker = "✓" if section in self.REQUIRED_SECTIONS else "•"
            report.append(f"  {marker} {section}")
        report.append("")
        
        # Errors
        if self.errors:
            report.append("ERRORS:")
            for error in self.errors:
                report.append(f"  ❌ {error}")
            report.append("")
        
        # Warnings
        if self.warnings:
            report.append("WARNINGS:")
            for warning in self.warnings:
                report.append(f"  ⚠️  {warning}")
            report.append("")
        
        report.append("=" * 60)
        return "\n".join(report)


def main():
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_architect_spec.py <spec_file>")
        sys.exit(1)
    
    spec_file = Path(sys.argv[1])
    
    if not spec_file.exists():
        print(f"Error: File not found: {spec_file}")
        sys.exit(1)
    
    # Read spec content
    content = spec_file.read_text()
    
    # Validate
    validator = ArchitectSpecValidator(content)
    is_valid, errors, warnings = validator.validate()
    
    # Print report
    print(validator.generate_report())
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
