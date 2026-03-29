from __future__ import annotations

import asyncio
from typing import Any, cast

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, LoadingIndicator, Static

from netui.collectors.traceroute import TraceHop, trace_route
from netui.utils.toast import show_toast
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class TraceroutePanel(PanelBase):
    BINDINGS = [
        Binding("t", "start_trace", "trace", show=False),
        Binding("escape", "cancel_trace", "cancel", show=False),
        Binding("r", "refresh_panel", "refresh", show=False),
    ]

    loading = reactive(True)
    running = reactive(False)
    progress_text = reactive("")
    error_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._hops: list[TraceHop] = []
        self._trace_task: asyncio.Task[None] | None = None
        self._target = "8.8.8.8"

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body"):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="trace-loading")
            with Horizontal():
                yield Static("Target:")
                yield Input(value="8.8.8.8", id="trace-target")
            yield Static("", id="trace-progress")
            yield Static("", id="trace-table")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "t": "re-run traceroute",
                "esc": "cancel",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        self.set_interval(1, self.update_stale_badge)
        self._render_all()

    def on_unmount(self) -> None:
        if self._trace_task and not self._trace_task.done():
            self._trace_task.cancel()

    def _latency_bar(self, latency_ms: float) -> str:
        values = [h["latency_ms"] for h in self._hops if not h["is_timeout"]]
        peak = max(values) if values else 1.0
        fill = int(round((latency_ms / max(peak, 1.0)) * 10))
        fill = max(0, min(10, fill))
        bar = "█" * fill + "░" * (10 - fill)
        if latency_ms < 50:
            color = "green"
        elif latency_ms <= 150:
            color = "yellow"
        else:
            color = "red"
        return f"[{color}]{bar}[/{color}]"

    def _render_table(self) -> None:
        table = Table(title="Traceroute Hops")
        table.add_column("Hop", justify="right")
        table.add_column("IP Address")
        table.add_column("Hostname")
        table.add_column("Latency")
        table.add_column("Bar")

        for hop in self._hops:
            if hop["is_timeout"]:
                table.add_row(str(hop["hop_num"]), "[dim]*[/dim]", "[dim]*[/dim]", "[dim]—[/dim]", "[dim]* * *[/dim]")
                continue

            latency = hop["latency_ms"]
            latency_str = f"{latency:.1f} ms"
            style = "green" if hop["ip"] == self._target else ""
            if style:
                table.add_row(
                    str(hop["hop_num"]),
                    f"[{style}]{hop['ip']}[/{style}]",
                    f"[{style}]{hop['hostname']}[/{style}]",
                    f"[{style}]{latency_str}[/{style}]",
                    self._latency_bar(latency),
                )
            else:
                table.add_row(
                    str(hop["hop_num"]),
                    hop["ip"],
                    hop["hostname"],
                    latency_str,
                    self._latency_bar(latency),
                )

        self.query_one("#trace-table", Static).update(table)

    def _render_all(self) -> None:
        self.query_one("#trace-loading", LoadingIndicator).display = self.loading
        self.query_one("#trace-progress", Static).update(self.progress_text)
        self._render_table()

    async def _run_trace(self, target: str) -> None:
        if self._trace_task and not self._trace_task.done():
            self._trace_task.cancel()

        self._target = target
        self._hops = []
        self.loading = True
        self.running = True
        self.error_text = ""
        self.progress_text = f"Tracing to {target}... (hop 0/30)"
        self._render_all()

        hop_count = 0
        try:
            async for hop in trace_route(target, max_hops=30):
                hop_count += 1
                self._hops.append(hop)
                self.progress_text = f"Tracing to {target}... (hop {hop_count}/30)"
                self.loading = False
                self._render_all()
        except asyncio.CancelledError:
            self.progress_text = f"Cancelled after {hop_count} hops"
            self.running = False
            self.loading = False
            self._render_all()
            return
        except Exception as exc:
            self.show_error(f"Collection failed: {exc}")
        finally:
            self.running = False
            self.loading = False
            if not self.error_text and self.progress_text.startswith("Tracing"):
                self.progress_text = f"Trace complete: {hop_count} hops"
                self.hide_error()
                self.mark_data_fresh(10)
                show_toast(cast(Any, self.app), "Traceroute complete", level="success")  # type: ignore[reportUnknownMemberType]
            self._render_all()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "trace-target":
            self.action_start_trace()

    def action_start_trace(self) -> None:
        target = self.query_one("#trace-target", Input).value.strip() or "8.8.8.8"
        self._trace_task = asyncio.create_task(self._run_trace(target))

    def start_trace(self) -> None:
        self.action_start_trace()

    def action_cancel_trace(self) -> None:
        if self._trace_task and not self._trace_task.done():
            self._trace_task.cancel()

    def refresh_data(self) -> None:
        self._hops = []
        self.action_start_trace()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self._hops = []
        self.progress_text = ""
        self.refresh_data()

    def cancel_operation(self) -> None:
        self.action_cancel_trace()

    def action_refresh_panel(self) -> None:
        self.refresh_data()
