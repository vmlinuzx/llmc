"""
Enrichment Config TUI - Interactive configuration editor for llmc.toml

A text-based user interface for managing enrichment chains, routes, and hierarchies
without directly editing TOML files.
"""

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static, Tree

from llmc.config.manager import ConfigManager


class RouteTreeView(Static):
    """Widget displaying the routing hierarchy as a tree."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        tree: Tree[dict] = Tree("Enrichment Configuration")
        tree.root.expand()

        enrichment = self.config.get("enrichment", {})
        routes = enrichment.get("routes", {})
        chains = enrichment.get("chain", [])
        default_chain = enrichment.get("default_chain", "unknown")

        # Build chain groups
        chain_groups: dict[str, list[dict]] = {}
        for chain in chains:
            group = chain.get("chain", "unknown")
            if group not in chain_groups:
                chain_groups[group] = []
            chain_groups[group].append(chain)

        # Sort chains within groups by tier
        tier_priority = {"nano": 0, "3b": 1, "7b": 2, "14b": 3, "70b": 4}
        for group in chain_groups:
            chain_groups[group] = sorted(
                chain_groups[group],
                key=lambda c: (
                    tier_priority.get(c.get("routing_tier", "7b"), 999),
                    c.get("name", ""),
                ),
            )

        # Display routed chains
        routes_node = tree.root.add("📋 Routed Chains", expand=True)
        for slice_type, chain_group in sorted(routes.items()):
            route_label = f"[bold cyan]{slice_type}[/] → {chain_group}"
            route_node = routes_node.add(route_label, expand=True)

            # Add chains in this group
            if chain_group in chain_groups:
                for idx, chain in enumerate(chain_groups[chain_group]):
                    name = chain.get("name", "unknown")
                    tier = chain.get("routing_tier", "?")
                    provider = chain.get("provider", "?")
                    model = chain.get("model", "?")
                    enabled = chain.get("enabled", True)

                    status = "✓" if enabled else "✗"
                    color = "green" if enabled else "dim"
                    order = "primary" if idx == 0 else "fallback"

                    chain_label = (
                        f"[{color}]{status} {name}[/] "
                        f"[dim]({tier}, {provider}, {order})[/]"
                    )
                    chain_node = route_node.add(chain_label)
                    chain_node.add_leaf(f"Model: {model}")

        # Display unrouted chains
        routed_groups = set(routes.values())
        unrouted_groups = set(chain_groups.keys()) - routed_groups

        if unrouted_groups:
            unrouted_node = tree.root.add("⚠️  Unrouted Chains", expand=False)
            for chain_group in sorted(unrouted_groups):
                group_label = f"[yellow]{chain_group}[/]"
                group_node = unrouted_node.add(group_label)

                for chain in chain_groups[chain_group]:
                    name = chain.get("name", "unknown")
                    enabled = chain.get("enabled", True)
                    status = "✓" if enabled else "✗"
                    color = "yellow" if enabled else "dim"

                    chain_label = f"[{color}]{status} {name}[/]"
                    group_node.add_leaf(chain_label)

        # Display default chain info
        info_node = tree.root.add("ℹ️  Configuration Info")
        info_node.add_leaf(f"Default Chain: {default_chain}")
        info_node.add_leaf(
            f"Routing Enabled: {enrichment.get('enable_routing', False)}"
        )
        info_node.add_leaf(f"Total Chains: {len(chains)}")
        info_node.add_leaf(f"Total Routes: {len(routes)}")

        yield tree


class DashboardScreen(Screen):
    """Main dashboard screen showing the enrichment hierarchy."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "simulate", "Simulate"),
        Binding("v", "validate", "Validate"),
        Binding("r", "reload", "Reload"),
    ]

    def __init__(self, manager: ConfigManager) -> None:
        super().__init__()
        self.manager = manager
        self.config = manager.config

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            RouteTreeView(self.config),
            Vertical(
                Static("[bold]Actions[/]", classes="section-title"),
                Button("Simulate Routing", id="btn-simulate", variant="primary"),
                Button("Validate Config", id="btn-validate", variant="success"),
                Button("Reload Config", id="btn-reload"),
                Button("Quit", id="btn-quit", variant="error"),
                classes="actions-panel",
            ),
            id="dashboard-container",
        )
        yield Footer()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_simulate(self) -> None:
        """Open routing simulator."""
        self.notify("Routing simulator not yet implemented")

    def action_validate(self) -> None:
        """Validate configuration."""
        errors = self.manager.validate(self.config)
        if errors:
            msg = "Validation errors:\n" + "\n".join(f"• {e}" for e in errors)
            self.notify(msg, severity="error", timeout=10)
        else:
            self.notify("✓ Configuration is valid!", severity="information")

    def action_reload(self) -> None:
        """Reload configuration from disk."""
        try:
            self.config = self.manager.load()
            self.refresh(layout=True)
            self.notify("✓ Configuration reloaded", severity="information")
        except Exception as e:
            self.notify(f"Failed to reload config: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-quit":
            self.action_quit()
        elif button_id == "btn-simulate":
            self.action_simulate()
        elif button_id == "btn-validate":
            self.action_validate()
        elif button_id == "btn-reload":
            self.action_reload()


class ConfigTUI(App):
    """Main TUI application for enrichment config management."""

    CSS = """
    #dashboard-container {
        layout: horizontal;
    }

    RouteTreeView {
        width: 3fr;
        height: 100%;
        border: solid green;
        padding: 1;
    }

    .actions-panel {
        width: 1fr;
        height: 100%;
        border: solid blue;
        padding: 1;
    }

    .section-title {
        text-align: center;
        padding: 1 0;
        background: $boost;
    }

    Button {
        width: 100%;
        margin: 1 0;
    }
    """

    TITLE = "LLMC Enrichment Config Editor"
    SUB_TITLE = "Safe visual editing of llmc.toml enrichment settings"

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config_path = config_path
        self.manager = ConfigManager(config_path)
        self.manager.load()

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(DashboardScreen(self.manager))


def run_tui(config_path: Path | None = None) -> None:
    """
    Launch the enrichment config TUI.

    Args:
        config_path: Path to llmc.toml. If None, searches for it in repo root.
    """
    if config_path is None:
        # Find repo root (look for llmc.toml)
        current = Path.cwd()
        while current != current.parent:
            candidate = current / "llmc.toml"
            if candidate.exists():
                config_path = candidate
                break
            current = current.parent

        if config_path is None:
            raise FileNotFoundError(
                "Could not find llmc.toml. Please run from repo root or specify path."
            )

    app = ConfigTUI(config_path)
    app.run()


if __name__ == "__main__":
    run_tui()
