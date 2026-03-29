from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static

_LEVEL_COLOR = {
    "info": "#79c0ff",
    "success": "#3fb950",
    "warning": "#e3b341",
    "error": "#f85149",
}


class _Toast(Widget):
    def __init__(self, message: str, level: str, duration: float) -> None:
        super().__init__()
        self._message = message
        self._level = level if level in _LEVEL_COLOR else "info"
        self._duration = duration

    def compose(self) -> ComposeResult:
        color = _LEVEL_COLOR[self._level]
        yield Static(f"[{color}]{self._message}[/{color}]", classes="toast-body")

    def on_mount(self) -> None:
        self.styles.dock = "top"
        self.styles.align_horizontal = "right"
        self.styles.width = "auto"
        self.styles.padding = (0, 1)
        self.styles.margin = (0, 1, 0, 0)
        self.set_timer(self._duration, self.remove)


def show_toast(app: App[Any], message: str, level: str = "info", duration: float = 3) -> None:
    severity_map = {
        "info": "information",
        "success": "information",
        "warning": "warning",
        "error": "error",
    }
    notify = getattr(app, "notify", None)
    if callable(notify):
        notify(
            message,
            severity=severity_map.get(level, "information"),
            timeout=duration,
        )
        return
    app.mount(_Toast(message=message, level=level, duration=duration))
