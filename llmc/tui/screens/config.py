import os
from pathlib import Path
import sys  # Import sys module

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Static

# Import RAG configuration tools
from llmc.rag.config import (
    embedding_device_preference,
    embedding_gpu_max_retries,
    embedding_gpu_min_free_mb,
    embedding_gpu_retry_seconds,
    embedding_model_dim,
    embedding_model_name,
    embedding_model_preset,
    embedding_normalize,
    embedding_passage_prefix,
    embedding_query_prefix,
    embedding_wait_for_gpu,
    index_path_for_read,
    load_rerank_weights,
)

# We might need to call find_repo_root from llmc.rag.utils
from llmc.rag.utils import find_repo_root


class ConfigScreen(Screen):
    """
    Displays current LLMC and RAG configuration, including environment variables.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    CSS = """
    ConfigScreen {
        layout: vertical;
        padding: 1;
        background: $surface;
    }

    #header {
        height: 3;
        border: heavy $primary;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    #config-container {
        border: heavy $secondary;
        padding: 1;
        background: $surface;
        height: 1fr;
    }

    .config-section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        border-bottom: solid $secondary;
    }

    .config-item {
        padding-left: 2;
        margin-bottom: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("LLMC Configuration", id="header")
        with ScrollableContainer(id="config-container"):
            yield Static("Loading configuration...", id="loading-message")
        yield Footer()

    def on_mount(self) -> None:
        self._display_config()

    def _display_config(self) -> None:
        container = self.query_one("#config-container")
        container.remove_children()

        repo_root = find_repo_root()

        # 1. System/App Environment Variables
        container.mount(
            Static("System & App Environment Variables", classes="config-section-title")
        )
        relevant_env_vars = {
            k: v
            for k, v in os.environ.items()
            if k.startswith(("LLMC_", "RAG_", "EMBEDDINGS_", "PYTHON"))
        }
        if relevant_env_vars:
            for k, v in sorted(relevant_env_vars.items()):
                container.mount(Static(f"[b]{k}[/b]: {v}", classes="config-item"))
        else:
            container.mount(
                Static(
                    "No specific LLMC/RAG related environment variables found.",
                    classes="config-item",
                )
            )
        container.mount(Static(""))  # Spacer

        # 2. RAG Configuration
        container.mount(Static("RAG Configuration", classes="config-section-title"))

        container.mount(Static(f"[b]Repo Root[/b]: {repo_root}", classes="config-item"))
        try:
            index_path = index_path_for_read(repo_root)
            container.mount(
                Static(f"[b]RAG Index DB[/b]: {index_path}", classes="config-item")
            )
            container.mount(
                Static(
                    f"[b]Index Exists[/b]: {index_path.exists()}", classes="config-item"
                )
            )
        except Exception as e:
            container.mount(
                Static(f"[b]RAG Index DB[/b]: Error - {e}", classes="config-item")
            )

        container.mount(Static(""))  # Spacer

        container.mount(Static("Embedding Model", classes="config-section-title"))
        container.mount(
            Static(f"[b]Preset[/b]: {embedding_model_preset()}", classes="config-item")
        )
        container.mount(
            Static(f"[b]Name[/b]: {embedding_model_name()}", classes="config-item")
        )
        container.mount(
            Static(f"[b]Dimension[/b]: {embedding_model_dim()}", classes="config-item")
        )
        container.mount(
            Static(
                f"[b]Passage Prefix[/b]: '{embedding_passage_prefix()}'",
                classes="config-item",
            )
        )
        container.mount(
            Static(
                f"[b]Query Prefix[/b]: '{embedding_query_prefix()}'",
                classes="config-item",
            )
        )
        container.mount(
            Static(f"[b]Normalize[/b]: {embedding_normalize()}", classes="config-item")
        )
        container.mount(
            Static(
                f"[b]Device Pref[/b]: {embedding_device_preference()}",
                classes="config-item",
            )
        )
        container.mount(
            Static(
                f"[b]Wait for GPU[/b]: {embedding_wait_for_gpu()}",
                classes="config-item",
            )
        )
        container.mount(
            Static(
                f"[b]GPU Min Free MB[/b]: {embedding_gpu_min_free_mb()}",
                classes="config-item",
            )
        )
        container.mount(
            Static(
                f"[b]GPU Max Retries[/b]: {embedding_gpu_max_retries()}",
                classes="config-item",
            )
        )
        container.mount(
            Static(
                f"[b]GPU Retry Seconds[/b]: {embedding_gpu_retry_seconds()}",
                classes="config-item",
            )
        )
        container.mount(Static(""))  # Spacer

        container.mount(Static("Reranker Weights", classes="config-section-title"))
        rerank_weights = load_rerank_weights(repo_root)
        for k, v in sorted(rerank_weights.items()):
            container.mount(Static(f"[b]{k}[/b]: {v:.4f}", classes="config-item"))
        container.mount(Static(""))  # Spacer

        # 3. Other (e.g., Python version, OS, etc.)
        container.mount(Static("System Information", classes="config-section-title"))
        container.mount(
            Static(
                f"[b]Python Version[/b]: {sys.version.splitlines()[0]}",
                classes="config-item",
            )
        )
        container.mount(
            Static(f"[b]Operating System[/b]: {sys.platform}", classes="config-item")
        )
        container.mount(
            Static(f"[b]Current Working Dir[/b]: {Path.cwd()}", classes="config-item")
        )
        container.mount(
            Static(f"[b]TUI CWD[/b]: {self.app.repo_root}", classes="config-item")
        )  # This is the app's repo_root, might be different than cwd
        container.mount(Static(""))  # Spacer
