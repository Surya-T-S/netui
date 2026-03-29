from __future__ import annotations

import asyncio
from typing import Any, cast

import psutil
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import DataTable, LoadingIndicator, Static

from netui.collectors.interfaces import InterfaceData, get_interfaces
from netui.utils.formatters import bytes_to_human
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class InterfacesPanel(PanelBase):
    BINDINGS = [Binding("r", "refresh_panel", "refresh", show=False)]

    loading = reactive(True)
    error_text = reactive("")
    selected_iface = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[InterfaceData] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body", can_focus=False):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="if-loading")
            yield DataTable(id="if-table")
            yield Static("", id="if-detail")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "↑↓": "select interface",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        table: DataTable[str] = self.query_one("#if-table", DataTable)  # type: ignore[assignment]
        table.cursor_type = "row"
        table.add_columns("Interface", "Type", "IPv4", "IPv6", "MAC", "MTU", "Speed", "State")
        self.set_interval(5, self._schedule_refresh)
        self.set_interval(1, self._refresh_detail_only)
        self.set_interval(1, self.update_stale_badge)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        asyncio.create_task(self._refresh_data())

    async def _refresh_data(self) -> None:
        self.loading = True
        self._render_misc()
        try:
            data = await get_interfaces()
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_misc()
            return
        self.loading = False
        self._rows = data
        if not data:
            self.show_error("No interfaces found")
            self._render_misc()
            self._render_table()
            self._render_detail()
            return
        self.hide_error()
        self.mark_data_fresh(5)
        if not self.selected_iface:
            self.selected_iface = data[0]["name"]
            cast(Any, self.app).active_interface = self.selected_iface  # type: ignore[reportUnknownMemberType]
        self._render_misc()
        self._render_table()
        self._render_detail()

    def _refresh_detail_only(self) -> None:
        if not self.selected_iface:
            return
        counters = psutil.net_io_counters(pernic=True).get(self.selected_iface)
        if counters is None:
            return
        for idx, row in enumerate(self._rows):
            if row["name"] == self.selected_iface:
                row["bytes_sent"] = int(counters.bytes_sent)
                row["bytes_recv"] = int(counters.bytes_recv)
                row["packets_sent"] = int(counters.packets_sent)
                row["packets_recv"] = int(counters.packets_recv)
                row["errin"] = int(counters.errin)
                row["errout"] = int(counters.errout)
                row["dropin"] = int(counters.dropin)
                row["dropout"] = int(counters.dropout)
                self._rows[idx] = row
                break
        self._render_detail()

    def _render_misc(self) -> None:
        self.query_one("#if-loading", LoadingIndicator).display = self.loading

    def _render_table(self) -> None:
        table: DataTable[str] = self.query_one("#if-table", DataTable)  # type: ignore[assignment]
        table.clear()
        for row in self._rows:
            state = "[bold green][UP][/bold green]" if row["is_up"] else "[red][DOWN][/red]"
            speed = f"{row['speed_mbps']} Mbps" if row["speed_mbps"] > 0 else "N/A"
            table.add_row(
                row["name"],
                row["type"],
                row["ipv4"] or "-",
                row["ipv6"] or "-",
                row["mac"] or "-",
                str(row["mtu"]),
                speed,
                state,
                key=row["name"],
            )

    def _render_detail(self) -> None:
        selected = next((r for r in self._rows if r["name"] == self.selected_iface), None)
        if not selected:
            self.query_one("#if-detail", Static).update("")
            return
        detail = "\n".join(
            [
                f"[bold]{selected['name']}[/bold]",
                f"IPv4: {selected['ipv4'] or '-'}",
                f"IPv6: {selected['ipv6'] or '-'}",
                f"Bytes sent/recv: {bytes_to_human(selected['bytes_sent'])} / {bytes_to_human(selected['bytes_recv'])}",
                f"Packets sent/recv: {selected['packets_sent']} / {selected['packets_recv']}",
                f"Errors in/out: {selected['errin']} / {selected['errout']}",
                f"Drops in/out: {selected['dropin']} / {selected['dropout']}",
            ]
        )
        self.query_one("#if-detail", Static).update(detail)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        value = event.row_key.value if event.row_key else ""
        if isinstance(value, str):
            self.selected_iface = value
            cast(Any, self.app).active_interface = value  # type: ignore[reportUnknownMemberType]
            self._render_detail()

    def refresh_data(self) -> None:
        self._schedule_refresh()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._rows = []
        self.selected_iface = ""
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.refresh_data()
