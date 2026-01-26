"""
Repository Onboarding Validator

Validates that a repository is properly configured for LLMC enrichment.
Catches issues that would cause silent failures:
- Missing [enrichment] section
- Missing enrichment chain definitions
- Missing [embeddings] configuration
- BOM characters in source files
- Unreachable Ollama endpoints

Usage:
    from llmc.commands.repo_validator import validate_repo, ValidationResult
    result = validate_repo(Path("/path/to/repo"))
    if not result.passed:
        for issue in result.issues:
            print(f"ERROR: {issue}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any

# Try to import tomllib (Python 3.11+) or fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: str  # "error", "warning", "info"
    category: str  # "config", "encoding", "connectivity", "structure"
    message: str
    fix_hint: str | None = None
    file_path: str | None = None

    def __str__(self) -> str:
        prefix = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "•")
        s = f"{prefix} [{self.category}] {self.message}"
        if self.fix_hint:
            s += f"\n   Fix: {self.fix_hint}"
        return s


@dataclass
class ValidationResult:
    """Result of repository validation."""

    repo_path: Path
    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    config: dict[str, Any] | None = None

    # Counts
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.error_count += 1
            self.passed = False
        elif issue.severity == "warning":
            self.warning_count += 1
        else:
            self.info_count += 1

    def add_error(
        self,
        category: str,
        message: str,
        fix_hint: str | None = None,
        file_path: str | None = None,
    ) -> None:
        self.add_issue(ValidationIssue("error", category, message, fix_hint, file_path))

    def add_warning(
        self,
        category: str,
        message: str,
        fix_hint: str | None = None,
        file_path: str | None = None,
    ) -> None:
        self.add_issue(
            ValidationIssue("warning", category, message, fix_hint, file_path)
        )

    def add_info(
        self,
        category: str,
        message: str,
        fix_hint: str | None = None,
        file_path: str | None = None,
    ) -> None:
        self.add_issue(ValidationIssue("info", category, message, fix_hint, file_path))

    def summary(self) -> str:
        """Return a one-line summary."""
        if self.passed:
            if self.warning_count > 0:
                return f"✅ Validation passed with {self.warning_count} warning(s)"
            return "✅ Validation passed"
        return f"❌ Validation failed: {self.error_count} error(s), {self.warning_count} warning(s)"


def check_llmc_toml_exists(repo_path: Path, result: ValidationResult) -> bool:
    """Check if llmc.toml exists."""
    config_path = repo_path / "llmc.toml"
    if not config_path.exists():
        result.add_error(
            "config",
            "No llmc.toml found",
            "Run 'llmc service repo add' to generate one, or create manually",
        )
        return False
    return True


def load_config(repo_path: Path, result: ValidationResult) -> dict[str, Any] | None:
    """Load and parse llmc.toml."""
    if tomllib is None:
        result.add_error(
            "config", "No TOML parser available (need Python 3.11+ or tomli package)"
        )
        return None

    config_path = repo_path / "llmc.toml"
    try:
        with config_path.open("rb") as f:
            config = tomllib.load(f)
        result.config = config
        return config
    except Exception as e:
        result.add_error("config", f"Failed to parse llmc.toml: {e}")
        return None


def check_enrichment_config(config: dict[str, Any], result: ValidationResult) -> None:
    """Check that enrichment is properly configured."""
    enrichment = config.get("enrichment")

    if not enrichment:
        result.add_error(
            "config",
            "Missing [enrichment] section - daemon won't know which LLM to use",
            "Add [enrichment] section with at least one [[enrichment.chain]] definition",
        )
        return

    # Check for chain definitions
    chains = enrichment.get("chain", [])
    if not chains:
        result.add_error(
            "config",
            "No [[enrichment.chain]] defined - no LLM backends configured",
            "Add at least one [[enrichment.chain]] with provider, model, and url",
        )
        return

    # Check that at least one chain is enabled
    enabled_chains = [c for c in chains if c.get("enabled", True)]
    if not enabled_chains:
        result.add_error(
            "config",
            "All enrichment chains are disabled",
            "Set enabled = true on at least one [[enrichment.chain]]",
        )
        return

    # Check each chain has required fields
    for i, chain in enumerate(enabled_chains):
        chain_name = chain.get("name", f"chain[{i}]")
        if not chain.get("provider"):
            result.add_warning(
                "config", f"Chain '{chain_name}' missing 'provider' field"
            )
        if not chain.get("model"):
            result.add_warning("config", f"Chain '{chain_name}' missing 'model' field")
        if chain.get("provider") == "ollama" and not chain.get("url"):
            result.add_warning(
                "config",
                f"Ollama chain '{chain_name}' missing 'url' field",
                'Add url = "http://localhost:11434" or your Ollama server address',
            )

    result.add_info(
        "config", f"Found {len(enabled_chains)} enabled enrichment chain(s)"
    )


def check_embeddings_config(config: dict[str, Any], result: ValidationResult) -> None:
    """Check that embeddings are properly configured."""
    embeddings = config.get("embeddings")

    if not embeddings:
        result.add_error(
            "config",
            "Missing [embeddings] section",
            "Add [embeddings] with default_profile and at least one profile definition",
        )
        return

    # Check for profiles
    profiles = embeddings.get("profiles", {})
    if not profiles:
        result.add_error(
            "config",
            "No embedding profiles defined in [embeddings.profiles]",
            "Add [embeddings.profiles.docs] with provider, model, and dimension",
        )
        return

    # Check for routes
    routes = embeddings.get("routes", {})
    if not routes:
        result.add_error(
            "config",
            "No embedding routes defined in [embeddings.routes]",
            "Add [embeddings.routes.docs] and [embeddings.routes.code] with profile and index",
        )
        return

    result.add_info(
        "config", f"Found {len(profiles)} embedding profile(s), {len(routes)} route(s)"
    )


def check_routing_config(config: dict[str, Any], result: ValidationResult) -> None:
    """Check slice type routing configuration."""
    routing = config.get("routing", {})
    slice_map = routing.get("slice_type_to_route", {})

    if not slice_map:
        result.add_warning(
            "config",
            "No [routing.slice_type_to_route] defined",
            "Add routing for: code, docs, config, data, other",
        )
        return

    # Check for common slice types
    expected_types = ["code", "docs"]
    missing = [t for t in expected_types if t not in slice_map]
    if missing:
        result.add_warning(
            "config",
            f"Missing routing for slice types: {', '.join(missing)}",
            'Add entries like: code = "code", docs = "docs"',
        )


def check_bom_characters(
    repo_path: Path, result: ValidationResult, extensions: list[str] | None = None
) -> list[Path]:
    """Scan for files with BOM characters."""
    if extensions is None:
        extensions = [
            ".py",
            ".ts",
            ".js",
            ".tsx",
            ".jsx",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".md",
        ]

    bom_files: list[Path] = []
    bom_bytes = b"\xef\xbb\xbf"

    # Get list of files to check
    try:
        for ext in extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                # Skip common exclusions
                rel_path = str(file_path.relative_to(repo_path))
                if any(
                    skip in rel_path
                    for skip in [
                        "node_modules",
                        ".git",
                        "__pycache__",
                        ".venv",
                        "venv",
                        ".next",
                        "dist",
                        "build",
                        ".llmc",
                    ]
                ):
                    continue

                try:
                    with file_path.open("rb") as f:
                        first_bytes = f.read(3)
                        if first_bytes == bom_bytes:
                            bom_files.append(file_path)
                except OSError:
                    continue
    except Exception:
        pass

    if bom_files:
        result.add_warning(
            "encoding",
            f"Found {len(bom_files)} file(s) with UTF-8 BOM characters",
            "Run with --fix-bom to strip them automatically",
        )
        for f in bom_files[:5]:  # Show first 5
            result.add_info(
                "encoding", f"  BOM in: {f.relative_to(repo_path)}", file_path=str(f)
            )
        if len(bom_files) > 5:
            result.add_info("encoding", f"  ... and {len(bom_files) - 5} more")

    return bom_files


def check_ollama_connectivity(config: dict[str, Any], result: ValidationResult) -> None:
    """Check if Ollama endpoints are reachable."""
    import urllib.error
    from urllib.parse import urlparse
    import urllib.request

    # Collect all Ollama URLs from enrichment chains
    urls_to_check: set[str] = set()

    enrichment = config.get("enrichment", {})
    for chain in enrichment.get("chain", []):
        if chain.get("provider") == "ollama" and chain.get("enabled", True):
            url = chain.get("url")
            if url:
                urls_to_check.add(url.rstrip("/"))

    # Also check embedding profiles
    for _profile_name, profile in (
        config.get("embeddings", {}).get("profiles", {}).items()
    ):
        if profile.get("provider") == "ollama":
            ollama_cfg = profile.get("ollama", {})
            api_base = ollama_cfg.get("api_base")
            if api_base:
                urls_to_check.add(api_base.rstrip("/"))

    if not urls_to_check:
        result.add_info("connectivity", "No Ollama endpoints configured to check")
        return

    for url in urls_to_check:
        # SECURITY: Only allow http/https schemes
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            result.add_error(
                "connectivity",
                f"Invalid URL scheme '{parsed.scheme}' in {url}. Only http/https allowed.",
                "Check your endpoint URL in llmc.toml",
            )
            continue

        try:
            # Try to hit the /api/tags endpoint (lists models)
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    result.add_info("connectivity", f"✓ Ollama reachable at {url}")
                else:
                    result.add_warning(
                        "connectivity", f"Ollama at {url} returned status {resp.status}"
                    )
        except urllib.error.URLError as e:
            result.add_error(
                "connectivity",
                f"Cannot reach Ollama at {url}: {e.reason}",
                "Check that Ollama is running and the URL is correct",
            )
        except Exception as e:
            result.add_warning("connectivity", f"Error checking {url}: {e}")


def check_required_models(config: dict[str, Any], result: ValidationResult) -> None:
    """Check if required models are available on Ollama."""
    import json
    import urllib.error
    import urllib.request

    # Collect models we need
    required_models: dict[str, str] = {}  # model -> url

    enrichment = config.get("enrichment", {})
    for chain in enrichment.get("chain", []):
        if chain.get("provider") == "ollama" and chain.get("enabled", True):
            model = chain.get("model")
            url = chain.get("url", "http://localhost:11434")
            if model:
                required_models[model] = url.rstrip("/")

    if not required_models:
        return

    # Group by URL and check
    url_to_models: dict[str, list[str]] = {}
    for model, url in required_models.items():
        url_to_models.setdefault(url, []).append(model)

    for url, models in url_to_models.items():
        try:
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                available = {m["name"] for m in data.get("models", [])}

                for model in models:
                    # Check exact match or partial match (model:tag vs model)
                    base_model = model.split(":")[0] if ":" in model else model
                    if model in available or any(base_model in a for a in available):
                        result.add_info("connectivity", f"✓ Model '{model}' available")
                    else:
                        result.add_warning(
                            "connectivity",
                            f"Model '{model}' not found on {url}",
                            f"Run: ollama pull {model}",
                        )
        except Exception:
            # Connectivity error already reported
            pass


def fix_bom_characters(bom_files: list[Path], result: ValidationResult) -> int:
    """Strip BOM characters from files."""
    fixed = 0
    bom_bytes = b"\xef\xbb\xbf"

    for file_path in bom_files:
        try:
            with file_path.open("rb") as f:
                content = f.read()

            if content.startswith(bom_bytes):
                with file_path.open("wb") as f:
                    f.write(content[3:])
                result.add_info("encoding", f"Fixed BOM in: {file_path}")
                fixed += 1
        except Exception as e:
            result.add_warning("encoding", f"Failed to fix {file_path}: {e}")

    return fixed


def validate_repo(
    repo_path: Path,
    *,
    check_connectivity: bool = True,
    check_models: bool = True,
    fix_bom: bool = False,
    verbose: bool = False,
) -> ValidationResult:
    """
    Validate a repository's LLMC configuration.

    Args:
        repo_path: Path to the repository root
        check_connectivity: Whether to test Ollama connectivity
        check_models: Whether to verify models are available
        fix_bom: Whether to automatically fix BOM characters
        verbose: Include extra info messages

    Returns:
        ValidationResult with all issues found
    """
    result = ValidationResult(repo_path=repo_path)

    # Check llmc.toml exists
    if not check_llmc_toml_exists(repo_path, result):
        return result

    # Load and parse config
    config = load_config(repo_path, result)
    if config is None:
        return result

    # Check required sections
    check_enrichment_config(config, result)
    check_embeddings_config(config, result)
    check_routing_config(config, result)

    # Check for BOM characters
    bom_files = check_bom_characters(repo_path, result)
    if fix_bom and bom_files:
        fixed = fix_bom_characters(bom_files, result)
        if fixed > 0:
            result.add_info("encoding", f"Fixed {fixed} file(s) with BOM characters")

    # Check connectivity (optional, can be slow)
    if check_connectivity and config:
        check_ollama_connectivity(config, result)
        if check_models:
            check_required_models(config, result)

    return result


def print_result(result: ValidationResult, verbose: bool = False) -> None:
    """Print validation result to console."""
    print(f"\n{'='*60}")
    print(f"Repository: {result.repo_path}")
    print(f"{'='*60}\n")

    if not result.issues:
        print("✅ No issues found!")
        return

    # Group by severity
    errors = [i for i in result.issues if i.severity == "error"]
    warnings = [i for i in result.issues if i.severity == "warning"]
    infos = [i for i in result.issues if i.severity == "info"]

    if errors:
        print("ERRORS:")
        for issue in errors:
            print(f"  {issue}")
        print()

    if warnings:
        print("WARNINGS:")
        for issue in warnings:
            print(f"  {issue}")
        print()

    if verbose and infos:
        print("INFO:")
        for issue in infos:
            print(f"  {issue}")
        print()

    print(f"\n{result.summary()}")


# CLI entry point
def main() -> int:
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate LLMC repository configuration"
    )
    parser.add_argument("repo_path", type=Path, help="Path to repository")
    parser.add_argument(
        "--no-connectivity", action="store_true", help="Skip connectivity checks"
    )
    parser.add_argument(
        "--no-models", action="store_true", help="Skip model availability checks"
    )
    parser.add_argument(
        "--fix-bom", action="store_true", help="Auto-fix BOM characters"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show all info messages"
    )

    args = parser.parse_args()

    result = validate_repo(
        args.repo_path,
        check_connectivity=not args.no_connectivity,
        check_models=not args.no_models,
        fix_bom=args.fix_bom,
        verbose=args.verbose,
    )

    print_result(result, verbose=args.verbose)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
