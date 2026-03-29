from __future__ import annotations

import asyncio
from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import LoadingIndicator, Static

from netui import config
from netui.collectors.wifi import WifiInfo, get_wifi_info
from netui.utils.sparkline import render_sparkline, smooth_values
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class WifiPanel(PanelBase):
    BINDINGS = [Binding("r", "refresh_panel", "refresh", show=False)]

    loading = reactive(True)
    error_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._data: WifiInfo | None = None
        self._signal_history: list[float] = []

    @staticmethod
    def _is_nonfatal_wifi_state(error: str) -> bool:
        text = error.lower()
        return any(
            token in text
            for token in (
                "not connected",
                "no wi-fi interface",
                "neither iw nor iwconfig",
                "not available",
            )
        )

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body", can_focus=False):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="wifi-loading")
            yield Static("", id="wifi-meter")
            yield Static("", id="wifi-grid")
            yield Static("", id="wifi-history")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        self.set_interval(config.WIFI_REFRESH_SECS, self._schedule_refresh)
        self.set_interval(1, self.update_stale_badge)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        asyncio.create_task(self._refresh_data())

    async def _refresh_data(self) -> None:
        self.loading = True
        self._render_view()
        try:
            data = await get_wifi_info()
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_view()
            return
        self.loading = False
        self._data = data
        err = data.get("error")
        if err:
            if self._is_nonfatal_wifi_state(str(err)):
                self.hide_error()
            else:
                self.show_error(str(err))
        else:
            self.hide_error()
            self.mark_data_fresh(config.WIFI_REFRESH_SECS)
        quality = data.get("quality_pct")
        if isinstance(quality, int):
            self._signal_history.append(float(quality))
            self._signal_history = self._signal_history[-60:]
        self._render_view()

    def _signal_meter(self, quality: int | None) -> str:
        if quality is None:
            return "[dim]▁ ▁ ▁ ▁[/dim]"
        if quality <= 25:
            return "[red]▂[/red] [dim]▄ ▆ █[/dim]"
        if quality <= 50:
            return "[red]▂[/red] [yellow]▄[/yellow] [dim]▆ █[/dim]"
        if quality <= 75:
            return "[yellow]▂▄[/yellow] [green]▆[/green] [dim]█[/dim]"
        return "[green]▂▄▆█[/green]"

    def _render_view(self) -> None:
        self.query_one("#wifi-loading", LoadingIndicator).display = self.loading
        if not self._data or self._data.get("error"):
            msg = "[dim][~][/dim]\n[bold]No Wi-Fi interface detected on this machine[/bold]"
            if self._data and self._data.get("error"):
                msg += f"\n[dim]{self._data.get('error')}[/dim]"
            self.query_one("#wifi-meter", Static).update(msg)
            self.query_one("#wifi-grid", Static).update("")
            self.query_one("#wifi-history", Static).update("")
            return

        quality = self._data.get("quality_pct")
        dbm = self._data.get("signal_dbm")
        self.query_one("#wifi-meter", Static).update(
            "\n".join(
                [
                    f"[bold]{self._signal_meter(quality if isinstance(quality, int) else None)}[/bold]",
                    f"Signal: {dbm if isinstance(dbm, (int, float)) else '-'} dBm / {quality if isinstance(quality, int) else '-'}%",
                ]
            )
        )
        self.query_one("#wifi-grid", Static).update(
            "\n".join(
                [
                    f"SSID          | {self._data.get('ssid') or '-'}",
                    f"BSSID         | {self._data.get('bssid') or '-'}",
                    f"Frequency     | {self._data.get('frequency_mhz') or '-'} MHz",
                    f"Channel       | {self._data.get('channel') or '-'}",
                    "Security      | N/A",
                    f"TX Rate       | {self._data.get('tx_bitrate_mbps') or '-'} Mbps",
                    "RX Rate       | N/A",
                    "Radio Type    | N/A",
                ]
            )
        )
        self.query_one("#wifi-history", Static).update(
            "Signal history (60s)\n"
            + render_sparkline(
                smooth_values(self._signal_history[-120:], alpha=0.3),
                width=max(24, min(120, self.size.width - 8)),
            )
        )

    def refresh_data(self) -> None:
        self._schedule_refresh()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._data = None
        self._signal_history = []
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.refresh_data()
