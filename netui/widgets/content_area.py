from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class ContentArea(Widget):
    """Mount target for the active module panel."""

    def compose(self) -> ComposeResult:
        yield Static(
            "Select a module from the sidebar", id="content-placeholder", classes="dim"
        )
