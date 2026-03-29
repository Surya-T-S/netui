from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import LoadingIndicator, ProgressBar, Static

from netui.collectors.speed import run_speed_test
from netui.utils.toast import show_toast
from netui.widgets.panel_base import PanelBase
from netui.widgets.status_bar import StatusBar


class SpeedPanel(PanelBase):
    BINDINGS = [
        Binding("s", "start_speed_test", "start", show=False),
        Binding("r", "refresh_panel", "refresh", show=False),
    ]

    download_mbps = reactive(0.0)
    upload_mbps = reactive(0.0)
    latency_ms = reactive(0.0)
    loading = reactive(True)
    running = reactive(False)
    phase_text = reactive("Connecting...")
    elapsed = reactive(0.0)
    last_run_iso = reactive("")
    error_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._log_lines: list[str] = []
        self._ticker = None
        self._run_started_at = 0.0
        self._last_progress_update = 0.0

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="panel-body"):
            yield Static("", id="stale-badge")
            yield LoadingIndicator(id="speed-loading")
            yield Static("Last run: Never run", id="speed-last-run")
            yield Static("", id="speed-large")
            yield ProgressBar(total=100, id="speed-progress")
            yield Static("Connecting...", id="speed-phase")
            yield Static("Elapsed: 0.0s", id="speed-elapsed")
            yield Static("", id="speed-log")

    def on_mount(self) -> None:
        cast(Any, self.app).query_one(StatusBar).update_hints(  # type: ignore[reportUnknownMemberType]
            {
                "tab": "cycle sidebar",
                "s": "start speed test",
                "r": "refresh",
                "q": "quit",
                "?": "help",
            }
        )
        self._ticker = self.set_interval(0.1, self._tick_elapsed)
        self.set_interval(30, self._render_last_run)
        self.set_interval(1, self.update_stale_badge)
        self._render_all()

    def _push_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_lines.append(f"[{ts}] {msg}")
        self._log_lines = self._log_lines[-10:]
        self.query_one("#speed-log", Static).update("\n".join(self._log_lines))

    def _tick_elapsed(self) -> None:
        if self.running:
            self.elapsed = max(0.0, time.monotonic() - self._run_started_at)
            self.query_one("#speed-elapsed", Static).update(f"Elapsed: {self.elapsed:.1f}s")

    def _render_last_run(self) -> None:
        if not self.last_run_iso:
            self.query_one("#speed-last-run", Static).update("Last run: Never run")
            return
        try:
            dt = datetime.fromisoformat(self.last_run_iso)
        except ValueError:
            self.query_one("#speed-last-run", Static).update("Last run: Unknown")
            return
        seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        if seconds < 60:
            rel = f"{seconds}s ago"
        else:
            rel = f"{seconds // 60}m ago"
        self.query_one("#speed-last-run", Static).update(f"Last run: {rel}")

    def _render_large(self) -> None:
        down = "—" if not self.last_run_iso else f"{self.download_mbps:.1f} Mbps"
        up = "—" if not self.last_run_iso else f"{self.upload_mbps:.1f} Mbps"
        lat = "—" if not self.last_run_iso else f"{self.latency_ms:.1f} ms"
        self.query_one("#speed-large", Static).update(
            "\n".join(
                [
                    f"[bold green]↓  {down}[/bold green]",
                    f"[bold cyan]↑  {up}[/bold cyan]",
                    f"[bold yellow]⌛  {lat}[/bold yellow]",
                ]
            )
        )

    def _render_all(self) -> None:
        progress = self.query_one("#speed-progress", ProgressBar)
        self.query_one("#speed-loading", LoadingIndicator).display = self.loading
        self.query_one("#speed-phase", Static).display = self.running
        self.query_one("#speed-elapsed", Static).display = self.running
        progress.display = self.running
        self._render_large()
        self._render_last_run()

    async def _progress_cb(self, phase: str, total_bytes: int, elapsed: float) -> None:
        now = time.monotonic()
        if now - self._last_progress_update < 0.2:
            return
        self._last_progress_update = now
        if phase == "download":
            self.phase_text = "Downloading..."
            done = min(75, int((total_bytes / 10_000_000) * 75))
            self.query_one("#speed-progress", ProgressBar).update(progress=done)
            mbps = (total_bytes * 8) / max(elapsed * 1_000_000, 1e-9)
            self._push_log(f"Downloading... {mbps:.1f} Mbps so far")
        self.query_one("#speed-phase", Static).update(self.phase_text)

    async def _run_test(self) -> None:
        if self.running:
            return
        self.running = True
        self.loading = False
        self.error_text = ""
        self.phase_text = "Connecting..."
        self._run_started_at = time.monotonic()
        self._last_progress_update = 0.0
        self.elapsed = 0.0
        self.query_one("#speed-progress", ProgressBar).update(progress=0)
        self._push_log("Starting speed test...")
        self._render_all()

        try:
            result = await run_speed_test(progress_callback=self._progress_cb)
        except Exception as exc:
            self.running = False
            self.show_error(f"Collection failed: {exc}")
            self._render_all()
            return

        self.phase_text = "Finishing..."
        self.query_one("#speed-phase", Static).update(self.phase_text)
        self.query_one("#speed-progress", ProgressBar).update(progress=100)

        self.download_mbps = float(result.get("download_mbps", 0.0))
        self.upload_mbps = float(result.get("upload_mbps", 0.0))
        self.latency_ms = float(result.get("latency_ms", 0.0))
        self.last_run_iso = str(result.get("timestamp", datetime.now(timezone.utc).isoformat()))
        self.error_text = str(result.get("error", "")) if result.get("error") else ""

        if self.error_text:
            self.show_error(self.error_text)
            self._push_log(f"Speed test failed: {self.error_text}")
        else:
            self.hide_error()
            self._push_log(f"Download complete: {self.download_mbps:.1f} Mbps")
            self._push_log(f"Upload complete: {self.upload_mbps:.1f} Mbps")
            self.mark_data_fresh(30)
            show_toast(cast(Any, self.app), "Speed test complete", level="success")  # type: ignore[reportUnknownMemberType]

        self.running = False
        self._render_all()

    def refresh_data(self) -> None:
        if not self.running:
            asyncio.create_task(self._run_test())

    def start_test(self) -> None:
        self.refresh_data()

    def open_filter(self) -> None:
        return

    def reset(self) -> None:
        self.download_mbps = 0.0
        self.upload_mbps = 0.0
        self.latency_ms = 0.0
        self.last_run_iso = ""
        self._log_lines = []
        self.query_one("#speed-log", Static).update("")

    def cancel_operation(self) -> None:
        self.running = False

    def action_start_speed_test(self) -> None:
        self.refresh_data()

    def action_refresh_panel(self) -> None:
        self.refresh_data()
