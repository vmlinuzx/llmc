"""Utility for downloading and caching the RAG models used by LLMC.

The previous version of this script failed immediately when the optional
`sentence-transformers` dependency was missing. That made it difficult to run
in new environments or CI where we only want to confirm that scripts wire up
correctly before pulling the fairly large model weights. This revision adds a
small CLI that can:

* Produce a dry-run plan with zero dependencies.
* Download through either Hugging Face *or* the system-wide Ollama daemon.
* Optionally install the Python dependencies from ``tools/rag/requirements.txt``
  when the user passes ``--install-missing-deps``.
* Emit actionable instructions when dependencies or model variants are absent.

When the dependencies are present the behaviour stays the same: we instantiate
each model so that Hugging Face downloads it into the local cache directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_FILE = PROJECT_ROOT / "tools" / "rag" / "requirements.txt"


@dataclass(frozen=True)
class ModelSpec:
    """Lightweight container so we can share metadata with the CLI."""

    name: str
    huggingface_identifier: str
    huggingface_loader: str  # ``sentence`` or ``cross``
    ollama_identifier: str | None = None
    ollama_default_tag: str | None = None


MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        "embedding-new",
        "intfloat/e5-base-v2",
        "sentence",
        "jeffh/intfloat-e5-base-v2",
        "q8_0",
    ),
    ModelSpec(
        "embedding-legacy",
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence",
        "all-minilm",
        "l6-v2",
    ),
    ModelSpec(
        "reranker",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "cross",
        None,
        None,
    ),
)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and cache the models used by LLMC's retrieval stack.",
    )
    parser.add_argument(
        "models",
        nargs="*",
        choices=[spec.name for spec in MODEL_SPECS],
        help="Only download a subset of the models (defaults to all).",
    )
    parser.add_argument(
        "--provider",
        choices=("huggingface", "ollama"),
        default="huggingface",
        help="Where to source the models from.",
    )
    parser.add_argument(
        "--ollama-tag",
        help=(
            "Override the default Ollama tag (quantization) for all models. "
            "Examples: q4_0, q8_0, f16."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which models would be downloaded without touching the network.",
    )
    parser.add_argument(
        "--install-missing-deps",
        action="store_true",
        help="Install Python dependencies from tools/rag/requirements.txt when missing (only for --provider huggingface).",
    )
    return parser.parse_args(list(argv))


def ensure_dependencies(auto_install: bool) -> tuple[Callable[[str], object], Callable[[str], object]]:
    """Import the heavy dependencies, installing them if requested."""

    try:
        from sentence_transformers import CrossEncoder, SentenceTransformer
    except ModuleNotFoundError as exc:
        if not auto_install:
            print(
                "Missing dependency: sentence-transformers.\n"
                "Install it via `pip install -r tools/rag/requirements.txt` or rerun with "
                "`--install-missing-deps`.",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

        print("sentence-transformers not found; installing required dependencies...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
            )
        except subprocess.CalledProcessError as install_exc:
            print(
                "Failed to install dependencies from tools/rag/requirements.txt.",
                file=sys.stderr,
            )
            raise SystemExit(1) from install_exc

        # Retry the import after installation.
        from sentence_transformers import CrossEncoder, SentenceTransformer  # type: ignore

    return SentenceTransformer, CrossEncoder


def _download_huggingface(
    spec: ModelSpec,
    sentence_loader: Callable[[str], object],
    cross_loader: Callable[[str], object],
) -> None:
    print(f"Downloading {spec.huggingface_identifier}...")
    if spec.huggingface_loader == "sentence":
        sentence_loader(spec.huggingface_identifier)
    elif spec.huggingface_loader == "cross":
        cross_loader(spec.huggingface_identifier)
    else:
        raise ValueError(f"Unknown loader type: {spec.huggingface_loader}")
    print(f"{spec.huggingface_identifier} downloaded.")


def _ollama_model_ref(spec: ModelSpec, override_tag: str | None) -> str:
    if spec.ollama_identifier is None:
        raise RuntimeError(
            f"No Ollama mapping configured for {spec.name}. Please use --provider huggingface."
        )

    tag = override_tag or spec.ollama_default_tag
    if tag:
        return f"{spec.ollama_identifier}:{tag}"
    return spec.ollama_identifier


def _download_ollama(spec: ModelSpec, override_tag: str | None) -> None:
    if shutil.which("ollama") is None:
        raise RuntimeError(
            "`ollama` CLI not found on PATH. Install Ollama from https://ollama.com/download and retry."
        )

    model_ref = _ollama_model_ref(spec, override_tag)
    cmd = ("ollama", "pull", model_ref)
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        hint = "Try a different quantization tag with --ollama-tag (e.g. q4_0, q8_0, f16)."
        raise RuntimeError(
            f"`ollama pull` failed for {model_ref}. {hint}\nOriginal error: {exc}"
        ) from exc
    print(f"{model_ref} downloaded via Ollama.")


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    selected_names = args.models or [spec.name for spec in MODEL_SPECS]
    selected_specs = [spec for spec in MODEL_SPECS if spec.name in selected_names]
    if not selected_specs:
        print("No models selected; nothing to do.")
        return 0

    if args.dry_run:
        print("Dry run: the following models would be downloaded:")
        for spec in selected_specs:
            if args.provider == "ollama":
                try:
                    identifier = _ollama_model_ref(spec, args.ollama_tag)
                except RuntimeError:
                    identifier = "<no-ollama-mapping>"
            else:
                identifier = spec.huggingface_identifier
            print(f"  - {spec.name}: {identifier}")
        return 0

    if args.provider == "ollama":
        for spec in selected_specs:
            try:
                _download_ollama(spec, args.ollama_tag)
            except RuntimeError as err:
                print(err, file=sys.stderr)
                return 1
    else:
        sentence_loader, cross_loader = ensure_dependencies(
            auto_install=args.install_missing_deps
        )
        for spec in selected_specs:
            _download_huggingface(spec, sentence_loader, cross_loader)

    print("\nAll models have been downloaded to the local cache.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
