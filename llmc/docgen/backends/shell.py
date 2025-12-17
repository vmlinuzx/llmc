"""
Shell backend for docgen - invokes external scripts for documentation generation.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import subprocess
from typing import Any

from llmc.docgen.types import DocgenResult

logger = logging.getLogger(__name__)


@dataclass
class ShellDocgenBackend:
    """Shell script backend for document generation.

    Invokes an external script with JSON input via stdin and parses the output.
    """

    script: Path
    args: list[str]
    timeout_seconds: int

    def generate_for_file(
        self,
        repo_root: Path,
        relative_path: Path,
        file_sha256: str,
        source_contents: str,
        existing_doc_contents: str | None,
        graph_context: str | None,
    ) -> DocgenResult:
        """Generate documentation by invoking shell script.

        Args:
            repo_root: Absolute path to repository root
            relative_path: Path relative to repo root
            file_sha256: SHA256 hash of source file
            source_contents: Contents of source file
            existing_doc_contents: Contents of existing doc (if any)
            graph_context: Graph context from RAG (if available)

        Returns:
            DocgenResult with status and generated content
        """
        # Build input JSON
        input_data = {
            "repo_root": str(repo_root),
            "relative_path": str(relative_path),
            "file_sha256": file_sha256,
            "source_contents": source_contents,
            "existing_doc_contents": existing_doc_contents,
            "graph_context": graph_context,
        }

        input_json = json.dumps(input_data)

        # Build command
        cmd = [str(self.script)] + self.args

        # Execute script
        # NOTE: check=False is INTENTIONAL. We want explicit exit code handling (line 90)
        # so we can log stderr on failure. Using check=True would raise CalledProcessError
        # and prevent our detailed logging. See: design_decisions.md
        try:
            result = subprocess.run(
                cmd,
                check=False,  # Explicit: we handle exit codes manually below
                input=input_json,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason=f"Script timed out after {self.timeout_seconds}s",
            )
        except Exception as e:
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason=f"Script execution failed: {e}",
            )

        # Check exit code
        if result.returncode != 0:
            logger.warning(
                f"Script exited with code {result.returncode}: {result.stderr}"
            )
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason=f"Script exited with code {result.returncode}",
            )

        # Parse output
        output = result.stdout.strip()

        # Check for NO-OP response
        if output.startswith("NO-OP:"):
            # Extract reason from "NO-OP: <reason>"
            reason = output[6:].strip()
            return DocgenResult(
                status="noop", sha256=file_sha256, output_markdown=None, reason=reason
            )

        # Check for SHA256 header
        if not output.startswith("SHA256:"):
            logger.error(f"Script output missing SHA256 header: {output[:100]}")
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason="Script output missing SHA256 header",
            )

        # Validate SHA256 matches
        first_line = output.split("\n", 1)[0]
        doc_sha = first_line[7:].strip()

        if doc_sha != file_sha256:
            logger.error(
                f"Script returned mismatched SHA256: "
                f"expected {file_sha256[:8]}..., got {doc_sha[:8]}..."
            )
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason="Script returned mismatched SHA256",
            )

        # Success - return generated doc
        return DocgenResult(
            status="generated", sha256=file_sha256, output_markdown=output, reason=None
        )


def load_shell_backend(
    repo_root: Path,
    config: dict[str, Any],
) -> ShellDocgenBackend:
    """Load shell backend from configuration.

    Args:
        repo_root: Absolute path to repository root
        config: [docs.docgen] configuration section

    Returns:
        ShellDocgenBackend instance

    Raises:
        ValueError: If configuration is invalid
    """
    # Get shell-specific config
    shell_config = config.get("shell", {})

    # Get script path
    script_str = shell_config.get("script")
    if not script_str:
        raise ValueError("Missing 'shell.script' in docgen configuration")

    # Resolve script path (relative to repo root)
    script_path = (repo_root / script_str).resolve()

    # Security: ensure script is within repo root
    if not str(script_path).startswith(str(repo_root.resolve())):
        raise ValueError(f"Docgen script is outside the repository root: {script_path}")

    if not script_path.exists():
        raise ValueError(f"Docgen script not found: {script_path}")

    if not script_path.is_file():
        raise ValueError(f"Docgen script is not a file: {script_path}")

    # Get optional args
    args = shell_config.get("args", [])
    if not isinstance(args, list):
        raise ValueError("'shell.args' must be a list")

    # Get timeout
    timeout = shell_config.get("timeout_seconds", 60)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("'shell.timeout_seconds' must be a positive number")

    return ShellDocgenBackend(
        script=script_path,
        args=args,
        timeout_seconds=int(timeout),
    )
