"""
LLMC TUI Base Screen - Foundation for all screens with standard navigation.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Static


class LLMCScreen(Screen):
    """
    Base class for all LLMC TUI screens.
    
    Provides:
    - Standard navigation bindings (1-8 for screens, q to quit, esc to go back)
    - Header with centered title
    - Bottom nav bar menu
    """

    BINDINGS = [
        Binding("1", "goto_dashboard", "Dashboard", show=False),
        Binding("2", "goto_search", "Search", show=False),
        Binding("3", "goto_service", "Service", show=False),
        Binding("4", "goto_nav", "Navigate", show=False),
        Binding("5", "goto_docs", "Docs", show=False),
        Binding("6", "goto_ruta", "RUTA", show=False),
        Binding("7", "goto_analytics", "Analytics", show=False),
        Binding("8", "goto_config", "Config", show=False),
        Binding("escape", "go_back", "Back", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    # Override in subclass
    SCREEN_TITLE = "LLMC"
    
    CSS = """
    .nav-bar {
        height: 3;
        background: #1a1a2e;
        border: heavy #00b8ff;
        padding: 0 1;
        dock: bottom;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose: Header + content + nav bar menu."""
        yield Header()
        yield from self.compose_content()
        yield self.build_nav_bar()

    def compose_content(self) -> ComposeResult:
        """Override this in subclasses to add screen content."""
        yield Static("Override compose_content() in your screen")

    def build_nav_bar(self) -> Static:
        """Build the navigation menu bar at bottom."""
        nav = (
            "[yellow](1)[/][#00ff9f]Dashboard[/]  "
            "[yellow](2)[/][#00ff9f]Search[/]  "
            "[yellow](3)[/][#00ff9f]Service[/]  "
            "[yellow](4)[/][#00ff9f]Nav[/]  "
            "[yellow](5)[/][#00ff9f]Docs[/]  "
            "[yellow](6)[/][#00ff9f]RUTA[/]  "
            "[yellow](7)[/][#00ff9f]Analytics[/]  "
            "[yellow](8)[/][#00ff9f]Config[/]  "
            "[yellow](esc)[/][#00ff9f]Back[/]  "
            "[yellow](q)[/][#00ff9f]Quit[/]"
        )
        return Static(nav, classes="nav-bar")

    def on_mount(self) -> None:
        """Set the header title."""
        self.app.title = "LARGE LANGUAGE MODEL COMPRESSOR"
        self.app.sub_title = ""

    # Navigation actions
    def action_goto_dashboard(self) -> None:
        """Switch to dashboard screen."""
        from llmc.tui.screens.dashboard import DashboardScreen
        self.app.switch_screen(DashboardScreen())

    def action_goto_search(self) -> None:
        """Switch to search screen."""
        from llmc.tui.screens.search import SearchScreen
        self.app.switch_screen(SearchScreen())

    def action_goto_service(self) -> None:
        """Switch to service management screen."""
        from llmc.tui.screens.service import ServiceScreen
        self.app.switch_screen(ServiceScreen())

    def action_goto_nav(self) -> None:
        """Switch to code navigation screen."""
        # TODO: Implement NavigateScreen
        self.notify("Navigate screen coming soon", severity="information")

    def action_goto_docs(self) -> None:
        """Switch to docs generation screen."""
        # TODO: Implement DocsScreen
        self.notify("Docs screen coming soon", severity="information")

    def action_goto_ruta(self) -> None:
        """Switch to RUTA testing screen."""
        try:
            from llmc.tui.screens.ruta import RUTAScreen
            self.app.switch_screen(RUTAScreen())
        except ImportError as e:
            self.notify(f"RUTA screen not available: {e}", severity="warning")

    def action_goto_analytics(self) -> None:
        """Switch to analytics screen."""
        try:
            from llmc.tui.screens.analytics import AnalyticsScreen
            self.app.switch_screen(AnalyticsScreen())
        except ImportError:
            self.notify("Analytics screen not available", severity="warning")

    def action_goto_config(self) -> None:
        """Switch to config editor screen."""
        try:
            from llmc.tui.screens.config import ConfigScreen
            self.app.switch_screen(ConfigScreen())
        except ImportError:
            self.notify("Config screen not available", severity="warning")

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.action_goto_dashboard()

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.app.exit()
