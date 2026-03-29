from __future__ import annotations

import asyncio
import statistics
from typing import Any, cast

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import LoadingIndicator, Static

from netui import config
from netui.collectors.latency import PingResult, ping_all_hosts
from netui.utils.async_runner import TaskScheduler
from netui.utils.formatters import ms_to_colored_str, pct_to_colored_str
from netui.utils.sparkline import render_sparkline, smooth_values
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class LatencyPanel(PanelBase):
    BINDINGS = [
        Binding("r", "refresh_panel", "refresh", show=False),
        Binding("h", "toggle_history", "toggle history", show=False),
    ]

    avg_latency = reactive(0.0)
    jitter = reactive(0.0)
    packet_loss = reactive(0.0)
    loading = reactive(True)
    error_text = reactive("")
    history_visible = reactive(True)

    def __init__(self) -> None:
        super().__init__()
        self._scheduler = TaskScheduler()
        self._history: list[float] = []
        self._rows: list[PingResult] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body"):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="latency-loading")
            with Horizontal(id="latency-stats"):
                yield Static("", id="latency-avg")
                yield Static("", id="latency-jitter")
                yield Static("", id="latency-loss")
            yield Static("Ping history (60s)", id="latency-history-label")
            yield Static("", id="latency-sparkline")
            yield Static("", id="latency-table")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "r": "refresh",
                "h": "toggle history",
                "q": "quit",
                "?": "help",
            }
        )
        self._render_stats()
        self._render_history()
        self._render_table()
        self.set_interval(1, self.update_stale_badge)
        self._scheduler.add_task("latency_poll", self._poll_once, config.PING_INTERVAL_SECS)
        asyncio.create_task(self._poll_once())

    def on_unmount(self) -> None:
        self._scheduler.cancel_all()

    async def _poll_once(self) -> None:
        try:
            results = await ping_all_hosts(config.DEFAULT_PING_HOSTS)
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self.update_stale_badge()
            return
        self.loading = False
        if not results:
            self.show_error("Unable to collect ping data")
            self._rows = []
            self._render_table()
            return

        self.hide_error()
        self._rows = results
        avg_values = [r["avg_ms"] for r in results]
        jitter_values = [r["jitter_ms"] for r in results]
        loss_values = [r["packet_loss_pct"] for r in results]

        self.avg_latency = statistics.mean(avg_values) if avg_values else 0.0
        self.jitter = statistics.mean(jitter_values) if jitter_values else 0.0
        self.packet_loss = statistics.mean(loss_values) if loss_values else 0.0
        self._history.append(self.avg_latency)
        self._history = self._history[-60:]
        self.mark_data_fresh(config.PING_INTERVAL_SECS)

        self._render_stats()
        self._render_history()
        self._render_table()
        self.query_one("#latency-loading", LoadingIndicator).display = self.loading

    def _render_stats(self) -> None:
        self.query_one("#latency-avg", Static).update(
            f"[bold]Avg Latency[/bold]\n{ms_to_colored_str(self.avg_latency)}"
        )
        self.query_one("#latency-jitter", Static).update(
            f"[bold]Jitter[/bold]\n{ms_to_colored_str(self.jitter)}"
        )
        self.query_one("#latency-loss", Static).update(
            f"[bold]Packet Loss[/bold]\n{pct_to_colored_str(self.packet_loss)}"
        )

    def _render_history(self) -> None:
        label = self.query_one("#latency-history-label", Static)
        spark = self.query_one("#latency-sparkline", Static)
        label.display = self.history_visible
        spark.display = self.history_visible
        if self.history_visible:
            width = max(24, min(120, self.size.width - 8))
            smooth = smooth_values(self._history, alpha=0.3)
            spark.update(f"[cyan]{render_sparkline(smooth, width=width)}[/cyan]")

    def _render_table(self) -> None:
        table = Table(title="Per-host ping")
        table.add_column("Host")
        table.add_column("Avg ms", justify="right")
        table.add_column("Min ms", justify="right")
        table.add_column("Max ms", justify="right")
        table.add_column("Loss %", justify="right")
        table.add_column("Status")

        for row in self._rows:
            avg = row["avg_ms"]
            style = "green" if avg < 50 else ("yellow" if avg <= 150 else "red")
            status = "[green]✓ alive[/green]" if row["is_alive"] else "[red]✗ down[/red]"
            table.add_row(
                row["host"],
                f"[{style}]{row['avg_ms']:.1f}[/{style}]",
                f"{row['min_ms']:.1f}",
                f"{row['max_ms']:.1f}",
                f"{row['packet_loss_pct']:.1f}",
                status,
            )

        self.query_one("#latency-table", Static).update(table)

    def refresh_data(self) -> None:
        asyncio.create_task(self._poll_once())

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._history = []
        self._rows = []
        self.refresh_data()

    def cancel_operation(self) -> None:
        self._scheduler.cancel_all()

    def action_refresh_panel(self) -> None:
        self.refresh_data()

    def action_toggle_history(self) -> None:
        self.history_visible = not self.history_visible
        self._render_history()
