from __future__ import annotations

import socket
from datetime import datetime, timezone

import httpx
import psutil
from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from netui.config import APP_NAME, PUBLIC_IP_URL


def _first_non_loopback_ipv4() -> str:
    for _iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not (
                addr.address.startswith("127.") or addr.address == "0.0.0.0"
            ):
                return addr.address
    return "—"


class Header(Widget):
    """Top bar: branding, host, IPs, UTC clock."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(APP_NAME, classes="header-brand")
            yield Static(" · ", classes="header-sep")
            yield Static("", id="header-host")
            yield Static(" · ", classes="header-sep")
            yield Static("", id="header-local-ip")
            yield Static(" · ", classes="header-sep")
            yield Static("…", id="header-public-ip")
            yield Static(" · ", classes="header-sep")
            yield Static("", id="header-clock")

    def on_mount(self) -> None:
        self.query_one("#header-host", Static).update(socket.gethostname())
        self.query_one("#header-local-ip", Static).update(_first_non_loopback_ipv4())
        self.set_interval(1.0, self.update_clock)
        self.update_clock()
        self.app.run_worker(self._fetch_public_ip(), exclusive=True)

    def update_clock(self) -> None:
        utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        self.query_one("#header-clock", Static).update(utc)

    async def _fetch_public_ip(self) -> None:
        static = self.query_one("#header-public-ip", Static)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(PUBLIC_IP_URL)
                response.raise_for_status()
                ip = response.text.strip()
            static.update(ip)
        except Exception:
            static.update(Text("?.?.?.?", style="dim"))
