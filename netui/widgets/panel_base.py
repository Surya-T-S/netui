from __future__ import annotations

import time

from textual.widget import Widget
from textual.widgets import Static

from netui.widgets.error_banner import ErrorBanner


class PanelBase(Widget):
    """Base for main content panels with shared refresh/filter/reset/error/stale helpers."""

    def __init__(self) -> None:
        super().__init__()
        self._last_data_at: float | None = None
        self._refresh_interval_secs: float = 5.0
        self._error_banner: ErrorBanner | None = None

    def refresh_data(self) -> None:
        pass

    def open_filter(self) -> None:
        pass

    def reset(self) -> None:
        pass

    def cancel_operation(self) -> None:
        pass

    def reload_data(self) -> None:
        self.refresh_data()

    def show_error(self, message: str) -> None:
        if self._error_banner is not None and not self._error_banner.is_attached:
            self._error_banner = None
        if self._error_banner is None:
            self._error_banner = ErrorBanner(message)
            self.mount(self._error_banner)
        else:
            try:
                self._error_banner.query_one("#error-message", Static).update(message)
            except Exception:
                pass

    def hide_error(self) -> None:
        if self._error_banner is not None and self._error_banner.is_attached:
            self._error_banner.remove()
        self._error_banner = None

    def mark_data_fresh(self, interval_secs: float) -> None:
        self._last_data_at = time.monotonic()
        self._refresh_interval_secs = interval_secs

    def update_stale_badge(self) -> None:
        try:
            badge = self.query_one("#stale-badge", Static)
        except Exception:
            return
        if self._last_data_at is None:
            badge.update("")
            return
        age = int(max(0.0, time.monotonic() - self._last_data_at))
        if age > int(self._refresh_interval_secs * 2):
            badge.update(f"[yellow][stale {age}s ago][/yellow]")
        else:
            badge.update("")
