from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static


class ErrorBanner(Widget):
    BINDINGS = [Binding("escape", "dismiss_banner", show=False)]

    DEFAULT_CSS = """
    ErrorBanner {
        background: $netui-header-bg;
        color: $netui-warning;
        border: round $netui-warning;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    ErrorBanner Button {
        width: 3;
        min-width: 3;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("⚠", id="error-icon")
            yield Static(self.message, id="error-message")
            yield Button("×", id="error-dismiss")

    def on_mount(self) -> None:
        return

    def action_dismiss_banner(self) -> None:
        self.remove()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "error-dismiss":
            self.remove()
