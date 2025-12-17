from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    """Run a subprocess command and fail the test on non-zero exit."""
    result = subprocess.run(cmd, check=False, cwd=str(REPO_ROOT))
    assert (
        result.returncode == 0
    ), f"{' '.join(cmd)} failed with code {result.returncode}"


def test_qwen_enrich_batch_ruff_clean() -> None:
    """Ensure ruff passes on qwen_enrich_batch script."""
    _run(
        [
            "ruff",
            "check",
            "scripts/qwen_enrich_batch.py",
        ]
    )


def test_qwen_enrich_batch_mypy_clean() -> None:
    """Ensure mypy passes on qwen_enrich_batch script."""
    _run(
        [
            "mypy",
            "--ignore-missing-imports",
            "scripts/qwen_enrich_batch.py",
        ]
    )
