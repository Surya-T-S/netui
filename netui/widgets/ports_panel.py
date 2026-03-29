from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import psutil
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, LoadingIndicator, Static

from netui import config
from netui.collectors.ports import OpenPortData, get_open_ports
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class ProcessDetailModal(ModalScreen[None]):
    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(self._text, classes="panel-body")


class PortsPanel(PanelBase):
    BINDINGS = [
        Binding("/", "focus_filter", "filter", show=False),
        Binding("r", "refresh_panel", "refresh", show=False),
    ]

    loading = reactive(True)
    error_text = reactive("")
    filter_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[OpenPortData] = []
        self._last_update = 0.0

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body"):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="ports-loading")
            yield Static("", id="ports-summary")
            with Horizontal():
                yield Static("Filter:")
                yield Input(placeholder="port, process, state", id="ports-filter")
            yield Static("", id="ports-updated")
            yield DataTable(id="ports-table")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "/": "filter",
                "r": "refresh",
                "↑↓": "navigate",
                "q": "quit",
                "?": "help",
            }
        )
        table: DataTable[str] = self.query_one("#ports-table", DataTable)  # type: ignore[assignment]
        table.cursor_type = "row"
        table.add_columns("PID", "Process", "Proto", "Local Address", "Port", "State", "Remote")
        self.set_interval(config.PORT_REFRESH_SECS, self._schedule_refresh)
        self.set_interval(1, self._update_last_updated)
        self.set_interval(1, self.update_stale_badge)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        asyncio.create_task(self._refresh_data())

    async def _refresh_data(self) -> None:
        self.loading = True
        self._render_misc()
        try:
            rows = await get_open_ports()
        except Exception as exc:
            self.loading = False
            self.show_error(f"Collection failed: {exc}")
            self._render_misc()
            return
        self.loading = False
        self._rows = rows
        self._last_update = time.monotonic()
        if rows:
            self.hide_error()
            self.mark_data_fresh(config.PORT_REFRESH_SECS)
        else:
            self.show_error("No open ports found")
        self._render_misc()
        self._render_table()

    def _filtered(self) -> list[OpenPortData]:
        if not self.filter_text:
            return self._rows
        needle = self.filter_text.lower()
        return [
            row
            for row in self._rows
            if needle in str(row["local_port"]).lower()
            or needle in row["process"].lower()
            or needle in row["state"].lower()
        ]

    def _render_misc(self) -> None:
        rows = self._filtered()
        listen = sum(1 for r in rows if r["state"] == "LISTEN")
        est = sum(1 for r in rows if r["state"] == "ESTABLISHED")
        other = max(0, len(rows) - listen - est)
        self.query_one("#ports-loading", LoadingIndicator).display = self.loading
        self.query_one("#ports-summary", Static).update(
            f"[cyan]LISTEN: {listen}[/cyan]  |  [green]ESTABLISHED: {est}[/green]  |  [dim]OTHER: {other}[/dim]"
        )
        self._update_last_updated()

    def _update_last_updated(self) -> None:
        if self._last_update <= 0:
            self.query_one("#ports-updated", Static).update("Last updated: -")
            return
        elapsed = int(max(0.0, time.monotonic() - self._last_update))
        self.query_one("#ports-updated", Static).update(f"Last updated: {elapsed}s ago")

    def _state_style(self, state: str) -> str:
        if state == "LISTEN":
            return "cyan"
        if state == "ESTABLISHED":
            return "green"
        if state == "CLOSE_WAIT":
            return "yellow"
        if state == "TIME_WAIT":
            return "yellow dim"
        return "dim"

    def _render_table(self) -> None:
        table: DataTable[str] = self.query_one("#ports-table", DataTable)  # type: ignore[assignment]
        table.clear()
        for row in self._filtered():
            style = self._state_style(row["state"])
            table.add_row(
                str(row["pid"] or "-"),
                f"[{style}]{row['process']}[/{style}]",
                row["proto"],
                row["local_ip"] or "*",
                str(row["local_port"]),
                f"[{style}]{row['state']}[/{style}]",
                f"{row['remote_ip']}:{row['remote_port']}" if row["remote_ip"] else "-",
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "ports-filter":
            self.filter_text = event.value
            self._render_misc()
            self._render_table()

    def action_focus_filter(self) -> None:
        self.query_one("#ports-filter", Input).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            row_idx = int(event.cursor_row)
        except Exception:
            return
        rows = self._filtered()
        if row_idx < 0 or row_idx >= len(rows):
            return
        row = rows[row_idx]
        pid = row["pid"]
        detail = [f"Process: {row['process']}"]
        if pid is not None:
            try:
                proc = psutil.Process(pid)
                detail.append(f"Path: {proc.exe()}")
                detail.append(f"User: {proc.username()}")
            except Exception:
                detail.append("Path: <unavailable>")
                detail.append("User: <unavailable>")
        else:
            detail.append("Path: <unknown>")
            detail.append("User: <unknown>")
        cast(Any, self.app).push_screen(ProcessDetailModal("\n".join(detail)))  # type: ignore[reportUnknownMemberType]

    def refresh_data(self) -> None:
        self._schedule_refresh()

    def open_filter(self) -> None:
        self.query_one("#ports-filter", Input).focus()

    def reset(self) -> None:
        self._rows = []
        self.filter_text = ""
        self.query_one("#ports-filter", Input).value = ""
        self.refresh_data()

    def cancel_operation(self) -> None:
        return

    def action_refresh_panel(self) -> None:
        self.refresh_data()
