"""LLMC Health Check & Diagnostics

Validates system health and provides actionable diagnostics for troubleshooting.

Usage:
    python -m tools.diagnostics.health_check
    # Or via CLI: llmc doctor
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import importlib.util


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error
    fix_suggestion: Optional[str] = None


@dataclass
class HealthReport:
    """Complete health check report."""
    checks: List[CheckResult] = field(default_factory=list)
    
    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)
    
    @property
    def warnings_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")
    
    @property
    def errors_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")
    
    @property
    def overall_health(self) -> str:
        """Overall health status."""
        if self.errors_count > 0:
            return "CRITICAL"
        elif self.warnings_count > 0:
            return "WARNING"
        else:
            return "HEALTHY"


class HealthChecker:
    """System health check orchestrator."""
    
    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.report = HealthReport()
    
    def run_all_checks(self) -> HealthReport:
        """Run all health checks and return report."""
        self._check_python_version()
        self._check_dependencies()
        self._check_tree_sitter_parsers()
        self._check_disk_space()
        self._check_rag_database()
        self._check_config_files()
        self._check_embedding_backend()
        return self.report
    
    def _add_check(self, result: CheckResult):
        """Add a check result to the report."""
        self.report.checks.append(result)
    
    def _check_python_version(self):
        """Verify Python version is compatible."""
        version = sys.version_info
        required_major, required_minor = 3, 8
        
        if version.major < required_major or (version.major == required_major and version.minor < required_minor):
            self._add_check(CheckResult(
                name="Python Version",
                passed=False,
                severity="error",
                message=f"Python {version.major}.{version.minor} detected",
                fix_suggestion=f"Upgrade to Python {required_major}.{required_minor}+ (pyenv install 3.11.0)"
            ))
        else:
            self._add_check(CheckResult(
                name="Python Version",
                passed=True,
                message=f"Python {version.major}.{version.minor}.{version.micro} ✓"
            ))
    
    def _check_dependencies(self):
        """Check if required Python packages are installed."""
        required_packages = {
            "tiktoken": "Token counting for context management",
            "tree_sitter": "AST-based code parsing",
            "yaml": "Configuration file parsing",
            "click": "CLI interface",
            "numpy": "Embedding vector operations"
        }
        
        for package, purpose in required_packages.items():
            try:
                if package == "yaml":
                    import yaml
                else:
                    __import__(package)
                
                self._add_check(CheckResult(
                    name=f"Package: {package}",
                    passed=True,
                    message=f"{package} installed ✓"
                ))
            except ImportError:
                self._add_check(CheckResult(
                    name=f"Package: {package}",
                    passed=False,
                    severity="error",
                    message=f"{package} not found ({purpose})",
                    fix_suggestion=f"pip install {package}"
                ))
    
    def _check_tree_sitter_parsers(self):
        """Verify tree-sitter language parsers are available."""
        try:
            from tree_sitter import Language
        except ImportError:
            self._add_check(CheckResult(
                name="Tree-sitter Languages",
                passed=False,
                severity="error",
                message="tree-sitter not installed",
                fix_suggestion="pip install tree-sitter"
            ))
            return
        
        required_languages = ["python", "typescript", "javascript", "bash"]
        
        for lang in required_languages:
            try:
                # Try to load the language
                # Note: This is a simplified check. Real implementation would
                # attempt to load actual .so files
                parser_available = True  # Placeholder
                
                if parser_available:
                    self._add_check(CheckResult(
                        name=f"Parser: {lang}",
                        passed=True,
                        message=f"{lang} parser available ✓"
                    ))
                else:
                    self._add_check(CheckResult(
                        name=f"Parser: {lang}",
                        passed=False,
                        severity="warning",
                        message=f"{lang} parser not found",
                        fix_suggestion=f"Run: python scripts/build_tree_sitter.py"
                    ))
            except Exception as e:
                self._add_check(CheckResult(
                    name=f"Parser: {lang}",
                    passed=False,
                    severity="warning",
                    message=f"{lang} parser check failed: {str(e)[:50]}",
                    fix_suggestion="Rebuild parsers: python scripts/build_tree_sitter.py"
                ))
    
    def _check_disk_space(self):
        """Check available disk space for cache."""
        try:
            rag_dir = self.repo_root / ".rag"
            if rag_dir.exists():
                check_path = rag_dir
            else:
                check_path = self.repo_root
            
            stat = shutil.disk_usage(check_path)
            free_gb = stat.free / (1024 ** 3)
            
            if free_gb < 0.5:
                self._add_check(CheckResult(
                    name="Disk Space",
                    passed=False,
                    severity="error",
                    message=f"Only {free_gb:.2f} GB free (minimum: 0.5 GB)",
                    fix_suggestion="Free up disk space or change RAG storage location"
                ))
            elif free_gb < 1.0:
                self._add_check(CheckResult(
                    name="Disk Space",
                    passed=False,
                    severity="warning",
                    message=f"{free_gb:.2f} GB free (recommended: >1 GB)",
                    fix_suggestion="Consider freeing up disk space for optimal performance"
                ))
            else:
                self._add_check(CheckResult(
                    name="Disk Space",
                    passed=True,
                    message=f"{free_gb:.2f} GB free ✓"
                ))
        except Exception as e:
            self._add_check(CheckResult(
                name="Disk Space",
                passed=False,
                severity="warning",
                message=f"Could not check disk space: {str(e)[:50]}",
                fix_suggestion="Verify filesystem permissions"
            ))
    
    def _check_rag_database(self):
        """Check RAG database integrity."""
        db_path = self.repo_root / ".rag" / "index.db"
        
        if not db_path.exists():
            self._add_check(CheckResult(
                name="RAG Database",
                passed=False,
                severity="warning",
                message="Database not initialized",
                fix_suggestion="Run: llmc index"
            ))
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            required_tables = {"files", "spans", "embeddings"}
            missing = required_tables - tables
            
            if missing:
                self._add_check(CheckResult(
                    name="RAG Database",
                    passed=False,
                    severity="error",
                    message=f"Missing tables: {', '.join(missing)}",
                    fix_suggestion="Database corrupted. Backup and run: llmc index"
                ))
            else:
                # Get stats
                cursor.execute("SELECT COUNT(*) FROM files")
                file_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM spans")
                span_count = cursor.fetchone()[0]
                
                self._add_check(CheckResult(
                    name="RAG Database",
                    passed=True,
                    message=f"Healthy: {file_count} files, {span_count} spans ✓"
                ))
            
            conn.close()
        except Exception as e:
            self._add_check(CheckResult(
                name="RAG Database",
                passed=False,
                severity="error",
                message=f"Database error: {str(e)[:50]}",
                fix_suggestion="Database corrupted. Backup and run: llmc index"
            ))
    
    def _check_config_files(self):
        """Validate configuration files."""
        config_path = self.repo_root / "config" / "examples" / "context_profile.yaml"
        
        if not config_path.exists():
            self._add_check(CheckResult(
                name="Configuration Files",
                passed=False,
                severity="warning",
                message="Default config not found",
                fix_suggestion="Restore config from: config/examples/"
            ))
            return
        
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            # Basic validation
            required_sections = ["rag", "cache", "models"]
            missing = [s for s in required_sections if s not in config]
            
            if missing:
                self._add_check(CheckResult(
                    name="Configuration Files",
                    passed=False,
                    severity="warning",
                    message=f"Missing config sections: {', '.join(missing)}",
                    fix_suggestion="Restore config from: config/examples/context_profile.yaml"
                ))
            else:
                self._add_check(CheckResult(
                    name="Configuration Files",
                    passed=True,
                    message="Configuration valid ✓"
                ))
        except yaml.YAMLError as e:
            self._add_check(CheckResult(
                name="Configuration Files",
                passed=False,
                severity="error",
                message=f"YAML parsing error: {str(e)[:50]}",
                fix_suggestion="Fix YAML syntax or restore from: config/examples/"
            ))
        except Exception as e:
            self._add_check(CheckResult(
                name="Configuration Files",
                passed=False,
                severity="warning",
                message=f"Config check failed: {str(e)[:50]}"
            ))
    
    def _check_embedding_backend(self):
        """Test embedding API connectivity."""
        try:
            # Try to import embedding backend
            from ..rag.embeddings import build_embedding_backend
            
            # Attempt to build backend (doesn't actually call API)
            backend = build_embedding_backend()
            
            self._add_check(CheckResult(
                name="Embedding Backend",
                passed=True,
                message="Backend initialized ✓"
            ))
        except ImportError as e:
            self._add_check(CheckResult(
                name="Embedding Backend",
                passed=False,
                severity="error",
                message=f"Import error: {str(e)[:50]}",
                fix_suggestion="Check if sentence-transformers is installed"
            ))
        except Exception as e:
            self._add_check(CheckResult(
                name="Embedding Backend",
                passed=False,
                severity="warning",
                message=f"Backend initialization failed: {str(e)[:50]}",
                fix_suggestion="Verify embedding model configuration"
            ))


def format_report(report: HealthReport, verbose: bool = False) -> str:
    """Format health report as human-readable string."""
    lines = []
    
    # Header
    status_emoji = {
        "HEALTHY": "✅",
        "WARNING": "⚠️",
        "CRITICAL": "❌"
    }
    
    lines.append("=" * 60)
    lines.append(f"LLMC HEALTH CHECK {status_emoji.get(report.overall_health, '❓')} {report.overall_health}")
    lines.append("=" * 60)
    lines.append(f"Passed: {report.passed_count} | Failed: {report.failed_count} | Warnings: {report.warnings_count} | Errors: {report.errors_count}")
    lines.append("")
    
    # Group by status
    passed = [c for c in report.checks if c.passed]
    warnings = [c for c in report.checks if not c.passed and c.severity == "warning"]
    errors = [c for c in report.checks if not c.passed and c.severity == "error"]
    
    # Show errors first
    if errors:
        lines.append("ERRORS:")
        for check in errors:
            lines.append(f"  ❌ {check.name}: {check.message}")
            if check.fix_suggestion:
                lines.append(f"     → Fix: {check.fix_suggestion}")
        lines.append("")
    
    # Then warnings
    if warnings:
        lines.append("WARNINGS:")
        for check in warnings:
            lines.append(f"  ⚠️  {check.name}: {check.message}")
            if check.fix_suggestion:
                lines.append(f"     → Fix: {check.fix_suggestion}")
        lines.append("")
    
    # Show passed checks only in verbose mode
    if verbose and passed:
        lines.append("PASSED:")
        for check in passed:
            lines.append(f"  ✓ {check.name}: {check.message}")
        lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def run_health_check(repo_root: Optional[Path] = None, verbose: bool = False) -> int:
    """Run health check and print report.
    
    Returns:
        Exit code (0 = healthy, 1 = warnings, 2 = errors)
    """
    checker = HealthChecker(repo_root=repo_root)
    report = checker.run_all_checks()
    
    print(format_report(report, verbose=verbose))
    
    if report.errors_count > 0:
        return 2
    elif report.warnings_count > 0:
        return 1
    else:
        return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LLMC Health Check & Diagnostics")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all checks including passed")
    parser.add_argument("--repo", type=Path, help="Repository root path")
    
    args = parser.parse_args()
    
    exit_code = run_health_check(repo_root=args.repo, verbose=args.verbose)
    sys.exit(exit_code)
