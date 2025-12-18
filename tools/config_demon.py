#!/usr/bin/env python3
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def log_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def log_warning(msg):
    print(f"{YELLOW}! {msg}{RESET}")

class ConfigValidator:
    def __init__(self, repo_root: Path, config_path: Path):
        self.repo_root = repo_root
        self.config_path = config_path
        self.config = {}
        self.errors = 0
        self.warnings = 0

    def load_config(self):
        if not self.config_path.exists():
            log_error(f"Config file not found: {self.config_path}")
            self.errors += 1
            return False

        try:
            with open(self.config_path, "rb") as f:
                self.config = tomllib.load(f)
            log_success("TOML Syntax is valid")
            return True
        except tomllib.TOMLDecodeError as e:
            log_error(f"TOML Syntax Error: {e}")
            self.errors += 1
            return False

    def validate_path(self, path_str: str, description: str, must_exist=True):
        # Handle absolute paths or relative to repo root
        path = Path(path_str)
        if not path.is_absolute():
            path = self.repo_root / path

        if not path.exists():
            if must_exist:
                log_warning(f"Path not found for {description}: {path}")
                self.warnings += 1
            return False
        return True

    def check_type(self, data: Dict, key: str, expected_types: tuple | type, context: str):
        if key not in data:
            return

        value = data[key]
        if not isinstance(value, expected_types):
            type_names = expected_types if isinstance(expected_types, tuple) else (expected_types,)
            expected = " or ".join([t.__name__ for t in type_names])
            log_error(f"Type mismatch for {context}.{key}: expected {expected}, got {type(value).__name__}")
            self.errors += 1

    def check_required_key(self, data: Dict, key: str, context: str):
        if key not in data:
            log_error(f"Missing required key: {context}.{key}")
            self.errors += 1
            return False
        return True

    def validate_schema(self):
        # Root sections
        required_sections = ["embeddings", "storage", "daemon", "enrichment", "mcp", "rag"]
        for section in required_sections:
            if not self.check_required_key(self.config, section, "root"):
                continue

        # Embeddings
        if "embeddings" in self.config:
            emb = self.config["embeddings"]
            self.check_type(emb, "default_profile", str, "embeddings")
            if "profiles" in emb:
                self.check_type(emb, "profiles", dict, "embeddings")
            if "routes" in emb:
                self.check_type(emb, "routes", dict, "embeddings")

        # Daemon
        if "daemon" in self.config:
            daemon = self.config["daemon"]
            self.check_type(daemon, "mode", str, "daemon")
            self.check_type(daemon, "debounce_seconds", (float, int), "daemon")

            # Deprecated checks
            if daemon.get("mode") == "poll":
                log_warning("daemon.mode = 'poll' is legacy/deprecated. Consider using 'event'.")
                self.warnings += 1

        # Logging
        if "logging" in self.config:
            logging = self.config["logging"]
            if "log_directory" in logging:
                # Log dir might be created at runtime, so we warn but don't error if missing?
                # Actually, usually we expect the dir to be creatable.
                # Let's check if parent exists at least.
                log_dir = logging["log_directory"]
                self.validate_path(log_dir, "logging.log_directory", must_exist=False)

        # Storage
        if "storage" in self.config:
            storage = self.config["storage"]
            if "index_path" in storage:
                # Index path might be a file that doesn't exist yet, but directory should probably exist
                # or at least be writeable.
                # Just warn if it doesn't exist
                self.validate_path(storage["index_path"], "storage.index_path", must_exist=False)

        # MCP
        if "mcp" in self.config:
            mcp = self.config["mcp"]
            self.check_type(mcp, "enabled", bool, "mcp")
            if "tools" in mcp:
                tools = mcp["tools"]
                if "allowed_roots" in tools:
                    roots = tools["allowed_roots"]
                    self.check_type(tools, "allowed_roots", list, "mcp.tools")
                    for root in roots:
                        if not Path(root).exists():
                            log_warning(f"MCP Allowed root does not exist: {root}")
                            self.warnings += 1

        # Deprecated Keys
        # Example: if we had a key 'old_setting' in root
        if "old_setting" in self.config:
            log_warning("Found deprecated key 'old_setting' in root")
            self.warnings += 1


    def run(self):
        print(f"Config Demon running on: {self.config_path}")
        if not self.load_config():
            return 1

        self.validate_schema()

        print("\nSummary:")
        if self.errors == 0:
            print(f"{GREEN}Validation Passed{RESET} with {self.warnings} warnings.")
            return 0
        else:
            print(f"{RED}Validation Failed{RESET} with {self.errors} errors and {self.warnings} warnings.")
            return 1

def main():
    repo_root = Path(os.environ.get("LLMC_ROOT", ".")).resolve()
    config_path = repo_root / "llmc.toml"

    validator = ConfigValidator(repo_root, config_path)
    sys.exit(validator.run())

if __name__ == "__main__":
    main()
