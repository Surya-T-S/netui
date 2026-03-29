from __future__ import annotations

from rich import box
from rich.table import Table

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class HelpScreen(ModalScreen[None]):
    """Modal reference for keyboard shortcuts."""

    BINDINGS = (
        Binding("escape", "close_help", show=False),
        Binding("question_mark", "close_help", "Dismiss", show=False, key_display="?"),
    )

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 76;
        max-height: 90%;
        background: $netui-header-bg;
        border: thick $netui-border;
        padding: 1 2;
        color: $netui-value;
    }
    #help-box .help-title {
        text-style: bold;
        color: $netui-accent;
        margin-bottom: 1;
    }
    #help-body {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="help-box"):
            with Vertical():
                yield Label("NetUI — Keyboard Reference", classes="help-title")
                yield Static(id="help-body")

    def on_mount(self) -> None:
        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold",
            expand=False,
        )
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Action")
        rows: list[tuple[str, str]] = [
            ("[bold]GLOBAL[/bold]", ""),
            ("q", "Quit the application"),
            ("Ctrl+C", "Quit (force)"),
            ("Tab", "Cycle sidebar sections"),
            ("↑ / ↓", "Navigate lists"),
            ("Enter", "Select item"),
            ("r", "Refresh current panel"),
            ("?", "Toggle this help screen"),
            ("Esc", "Cancel / close"),
            ("c", "Cycle color theme"),
            ("PgUp / PgDn", "Scroll panel"),
            ("Ctrl+L", "Reset / clear panel"),
            ("[bold]PANEL-SPECIFIC[/bold]", ""),
            ("/ (slash)", "Open filter input"),
            ("s", "Start speed test (Speed panel)"),
            ("t", "Run traceroute (Traceroute panel)"),
            ("i", "Cycle interface (Bandwidth panel)"),
            ("Enter", "DNS lookup (DNS panel)"),
            ("Esc", "Cancel trace (Traceroute panel)"),
        ]
        for key, desc in rows:
            table.add_row(key, desc)
        self.query_one("#help-body", Static).update(table)
        self.mount(Label("Press Esc or ? to close", classes="dim"))

    def action_close_help(self) -> None:
        self.dismiss()
