from __future__ import annotations

from rich.text import Text

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


DEFAULT_HINTS: dict[str, str] = {
    "tab": "cycle sidebar",
    "↑↓": "navigate",
    "r": "refresh",
    "q": "quit",
    "?": "help",
    "/": "filter",
}


class StatusBar(Widget):
    """Footer key hints; panels may replace hints via `update_hints`."""

    _hints: dict[str, str] = DEFAULT_HINTS.copy()

    def compose(self) -> ComposeResult:
        yield Static(id="status-hints")

    def on_mount(self) -> None:
        self._render_hints()

    def update_hints(self, hints: dict[str, str]) -> None:
        self._hints = dict(hints)
        self._render_hints()

    def reset_hints(self) -> None:
        self._hints = DEFAULT_HINTS.copy()
        self._render_hints()

    def redraw(self) -> None:
        self._render_hints()

    def _render_hints(self) -> None:
        row = Text()
        accent = self.app.theme_variables.get("netui-accent", "#58a6ff")  # type: ignore[reportUnknownMemberType]
        for key, desc in self._hints.items():
            row.append(f"[{key}] ", style=f"bold {accent}")
            row.append(f"{desc}  ", style="dim")
        self.query_one("#status-hints", Static).update(row)
