from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import LoadingIndicator, Static

from netui import config
from netui.collectors.bandwidth import BandwidthMonitor, InterfaceBandwidth
from netui.utils.formatters import bytes_to_human
from netui.utils.sparkline import render_sparkline, smooth_values
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class BandwidthPanel(PanelBase):
    BINDINGS = [
        Binding("i", "cycle_interface", "cycle", show=False),
        Binding("r", "refresh_panel", "refresh", show=False),
    ]

    loading = reactive(True)
    error_text = reactive("")
    active_iface = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._monitor = BandwidthMonitor()
        self._latest: dict[str, InterfaceBandwidth] = {}
        self._started = datetime.now()

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body", can_focus=False):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="bw-loading")
            yield Static("Interface: -", id="bw-selector")
            yield Static("", id="bw-rx")
            yield Static("", id="bw-tx")
            yield Static("", id="bw-summary")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "i": "cycle interface",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        self.set_interval(config.BANDWIDTH_POLL_SECS, self._schedule_poll)
        self.set_interval(1, self.update_stale_badge)
        self._schedule_poll()

    def _schedule_poll(self) -> None:
        asyncio.create_task(self._poll_once())

    async def _poll_once(self) -> None:
        try:
            data = await self._monitor.poll()
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_view()
            return
        if data:
            self.loading = False
            self.hide_error()
            self._latest = data
            if not self.active_iface or self.active_iface not in self._latest:
                self.active_iface = sorted(self._latest.keys())[0]
            self.mark_data_fresh(config.BANDWIDTH_POLL_SECS)
        else:
            self.loading = False
            if not self._latest:
                self.hide_error()
        self._render_view()

    def _chart(self, values: list[float], color: str) -> str:
        width = max(24, min(120, self.size.width - 16))
        smooth = smooth_values(values[-120:], alpha=0.28)
        return f"[{color}]" + render_sparkline(smooth, width=width) + f"[/{color}]"

    def _render_view(self) -> None:
        self.query_one("#bw-loading", LoadingIndicator).display = self.loading

        if not self.active_iface or self.active_iface not in self._latest:
            self.query_one("#bw-selector", Static).update("Interface: -  [i] to cycle")
            self.query_one("#bw-rx", Static).update("Collecting data...")
            self.query_one("#bw-tx", Static).update("")
            self.query_one("#bw-summary", Static).update("")
            return

        sample = self._latest[self.active_iface]
        rx_now = bytes_to_human(sample["rx_bps"]) + "/s"
        tx_now = bytes_to_human(sample["tx_bps"]) + "/s"
        rx_peak = bytes_to_human(max(sample["rx_history"], default=0.0)) + "/s"
        tx_peak = bytes_to_human(max(sample["tx_history"], default=0.0)) + "/s"

        self.query_one("#bw-selector", Static).update(
            f"Interface: [bold]{self.active_iface}[/bold]  [i] to cycle"
        )
        self.query_one("#bw-rx", Static).update(
            f"[bold]↓ RX  {rx_now}  (peak: {rx_peak})[/bold]\n{self._chart(sample['rx_history'], 'cyan')}"
        )
        self.query_one("#bw-tx", Static).update(
            f"[bold]↑ TX  {tx_now}  (peak: {tx_peak})[/bold]\n{self._chart(sample['tx_history'], 'green')}"
        )
        self.query_one("#bw-summary", Static).update(
            " | ".join(
                [
                    f"Total RX: {bytes_to_human(sample['total_rx'])}",
                    f"Total TX: {bytes_to_human(sample['total_tx'])}",
                    f"Active since: {self._started.strftime('%H:%M:%S')}",
                ]
            )
        )

    def action_cycle_interface(self) -> None:
        if not self._latest:
            return
        names = sorted(self._latest.keys())
        if self.active_iface not in names:
            self.active_iface = names[0]
        else:
            idx = names.index(self.active_iface)
            self.active_iface = names[(idx + 1) % len(names)]
        self._render_view()

    def cycle_interface(self) -> None:
        self.action_cycle_interface()

    def refresh_data(self) -> None:
        self._schedule_poll()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._monitor = BandwidthMonitor()
        self._latest = {}
        self.loading = True
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.reset()
