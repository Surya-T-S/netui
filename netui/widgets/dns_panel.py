from __future__ import annotations

import asyncio
from typing import Any, cast

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, LoadingIndicator, Static

from netui import config
from netui.collectors.dns import DnsResolveResult, bulk_resolve, resolve_host
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class DnsPanel(PanelBase):
    BINDINGS = [
        Binding("r", "refresh_panel", "refresh", show=False),
        Binding("/", "focus_filter", "filter", show=False),
    ]

    loading = reactive(True)
    error_text = reactive("")
    filter_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._results: list[DnsResolveResult] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body"):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="dns-loading")
            with Horizontal():
                yield Static("Lookup:")
                yield Input(placeholder="google.com", id="dns-lookup-input")
            with Horizontal(id="dns-filter-row"):
                yield Static("Filter:")
                yield Input(placeholder="hostname filter", id="dns-filter-input")
            yield Static("", id="dns-table")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "/": "filter",
                "r": "refresh",
                "enter": "lookup",
                "q": "quit",
                "?": "help",
            }
        )
        self._render_view()
        self.set_interval(1, self.update_stale_badge)
        asyncio.create_task(self._load_initial())

    async def _load_initial(self) -> None:
        self.loading = True
        self._render_view()
        try:
            self._results = await bulk_resolve(config.DEFAULT_DNS_TEST_HOSTS)
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_view()
            return
        self.loading = False
        if not self._results:
            self.show_error("No DNS responses received")
        else:
            self.hide_error()
            self.mark_data_fresh(10)
        self._render_view()

    async def _lookup_single(self, host: str) -> None:
        if not host.strip():
            return
        self.loading = True
        self._render_view()
        try:
            result = await resolve_host(host.strip())
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_view()
            return
        self.loading = False
        self._results = [result] + [r for r in self._results if r["hostname"] != result["hostname"]]
        self._results.sort(key=lambda row: row["query_time_ms"])
        self.hide_error()
        self.mark_data_fresh(10)
        self._render_view()

    def _render_table(self) -> None:
        table = Table(title="DNS Results")
        table.add_column("Host")
        table.add_column("IP Addresses")
        table.add_column("TTL", justify="right")
        table.add_column("Query Time", justify="right")
        table.add_column("Resolver")
        table.add_column("Status")

        filtered = self._results
        if self.filter_text:
            needle = self.filter_text.lower()
            filtered = [r for r in self._results if needle in r["hostname"].lower()]

        for row in sorted(filtered, key=lambda r: r["query_time_ms"]):
            q_ms = row["query_time_ms"]
            if q_ms < 20:
                q_style = "green"
            elif q_ms <= 100:
                q_style = "yellow"
            else:
                q_style = "red"

            status = "[green]OK[/green]" if not row["error"] else f"[red]{row['error']}[/red]"
            table.add_row(
                row["hostname"],
                ", ".join(row["ip_list"]) if row["ip_list"] else "-",
                str(row["ttl"]),
                f"[{q_style}]{q_ms:.1f} ms[/{q_style}]",
                row["resolver"] or "-",
                status,
            )

        self.query_one("#dns-table", Static).update(table)

    def _render_view(self) -> None:
        self.query_one("#dns-loading", LoadingIndicator).display = self.loading
        self._render_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "dns-lookup-input":
            asyncio.create_task(self._lookup_single(event.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "dns-filter-input":
            self.filter_text = event.value
            self._render_table()

    def action_focus_filter(self) -> None:
        self.query_one("#dns-filter-input", Input).focus()

    def refresh_data(self) -> None:
        asyncio.create_task(self._load_initial())

    def open_filter(self) -> None:
        self.query_one("#dns-filter-input", Input).focus()

    def reset(self) -> None:
        self._results = []
        self.filter_text = ""
        self.query_one("#dns-filter-input", Input).value = ""
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.refresh_data()
