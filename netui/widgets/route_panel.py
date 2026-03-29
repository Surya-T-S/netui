from __future__ import annotations

import asyncio
import ipaddress
from typing import Any, cast

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import LoadingIndicator, Static

from netui.collectors.routes import get_routes
from netui.utils.charts import ratio_bar
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class RoutePanel(PanelBase):
    BINDINGS = [Binding("r", "refresh_panel", "refresh", show=False)]

    loading = reactive(True)
    error_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._routes: list[dict[str, object]] = []
        self._has_loaded_once = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body", can_focus=False):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="route-loading")
            yield Static("", id="route-summary")
            yield Static("", id="route-ipv4")
            yield Static("", id="route-ipv6")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        self.set_interval(1, self.update_stale_badge)
        self.reload_data()

    def _schedule_refresh(self) -> None:
        asyncio.create_task(self._refresh_data())

    async def _refresh_data(self) -> None:
        self.loading = not self._has_loaded_once
        self._render_view()
        try:
            self._routes = await get_routes()
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_view()
            return
        self.loading = False
        if self._routes:
            self._has_loaded_once = True
            self.hide_error()
            self.mark_data_fresh(10)
        else:
            self.show_error("No routes found")
        self._render_view()

    def _sort_key(self, row: dict[str, object]) -> tuple[int, int]:
        destination = str(row.get("destination", "0.0.0.0"))
        is_default = 0 if destination == "0.0.0.0" else 1
        try:
            ip_num = int(ipaddress.ip_address(destination))
        except ValueError:
            ip_num = 0
        return (is_default, ip_num)

    @staticmethod
    def _metric_value(row: dict[str, object]) -> int:
        raw = row.get("metric", 0)
        try:
            return int(raw)  # type: ignore[arg-type]
        except Exception:
            return 0

    def _render_view(self) -> None:
        self.query_one("#route-loading", LoadingIndicator).display = self.loading

        ipv4 = [r for r in self._routes if ":" not in str(r.get("destination", ""))]
        ipv6 = [r for r in self._routes if ":" in str(r.get("destination", ""))]
        ipv4_sorted = sorted(ipv4, key=self._sort_key)

        default_row = next((r for r in ipv4_sorted if str(r.get("destination")) == "0.0.0.0"), None)
        if default_row:
            self.query_one("#route-summary", Static).update(
                f"Default Gateway: [bold]{default_row.get('gateway', '-')}[/bold]  via  [bold]{default_row.get('interface', '-')}[/bold]"
            )
        else:
            self.query_one("#route-summary", Static).update("Default Gateway: -")

        t4 = Table(title="IPv4 Routes")
        t4.add_column("Destination")
        t4.add_column("Mask")
        t4.add_column("Gateway")
        t4.add_column("Interface")
        t4.add_column("Metric", justify="right")
        t4.add_column("Graph")
        t4.add_column("Default")
        peak_metric = max((self._metric_value(r) for r in ipv4_sorted), default=1)
        for r in ipv4_sorted:
            is_default = str(r.get("destination", "")) == "0.0.0.0"
            star = "★" if is_default else ""
            metric = self._metric_value(r)
            graph = ratio_bar(float(metric), float(peak_metric), width=10)
            if is_default:
                t4.add_row(
                    f"[black on cyan]{r.get('destination', '-')}[/black on cyan]",
                    f"[black on cyan]{r.get('mask', '-')}[/black on cyan]",
                    f"[black on cyan]{r.get('gateway', '-')}[/black on cyan]",
                    f"[black on cyan]{r.get('interface', '-')}[/black on cyan]",
                    f"[black on cyan]{metric}[/black on cyan]",
                    f"[black on cyan]{graph}[/black on cyan]",
                    f"[black on cyan]{star}[/black on cyan]",
                )
            else:
                t4.add_row(
                    str(r.get("destination", "-")),
                    str(r.get("mask", "-")),
                    str(r.get("gateway", "-")),
                    str(r.get("interface", "-")),
                    str(metric),
                    graph,
                    star,
                )
        self.query_one("#route-ipv4", Static).update(t4)

        if ipv6:
            t6 = Table(title="IPv6 Routes")
            t6.add_column("Destination")
            t6.add_column("Mask")
            t6.add_column("Gateway")
            t6.add_column("Interface")
            t6.add_column("Metric", justify="right")
            t6.add_column("Default")
            for r in ipv6:
                t6.add_row(
                    str(r.get("destination", "-")),
                    str(r.get("mask", "-")),
                    str(r.get("gateway", "-")),
                    str(r.get("interface", "-")),
                    str(r.get("metric", "-")),
                    "",
                )
            self.query_one("#route-ipv6", Static).update(t6)
        else:
            self.query_one("#route-ipv6", Static).update("[dim]No IPv6 routes configured[/dim]")

    def refresh_data(self) -> None:
        self._schedule_refresh()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._routes = []
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.refresh_data()
